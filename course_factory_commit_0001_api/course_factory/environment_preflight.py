from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from .hpc_settings import HPCSettings


def _container_prefix(settings: HPCSettings) -> list[str]:
    if shutil.which("apptainer") is None:
        raise RuntimeError("Missing executable: apptainer")

    image = settings.apptainer_image
    if image is None:
        raise RuntimeError("APPTAINER_IMAGE is not configured")
    if not image.is_file():
        raise RuntimeError(
            f"Apptainer image does not exist: {image}"
        )

    return [
        "apptainer",
        "exec",
        "--cleanenv",
        "--containall",
        "--no-home",
        "--net",
        "--network",
        "none",
        str(image),
    ]


def run_environment_preflight(
    *,
    settings: HPCSettings,
    required_r_packages: tuple[str, ...] = (),
    require_slurm: bool = False,
) -> dict:
    problems: list[str] = []
    warnings: list[str] = []
    installed_packages: dict[str, str] = {}

    if require_slurm:
        for executable in ("sbatch", "squeue", "scancel"):
            if shutil.which(executable) is None:
                problems.append(
                    f"Missing SLURM executable: {executable}"
                )

    disallowed = sorted(
        set(required_r_packages)
        - set(settings.allowed_r_packages)
    )
    if disallowed:
        problems.append(
            "R packages are not allow-listed: "
            + ", ".join(disallowed)
        )

    try:
        prefix = _container_prefix(settings)
    except RuntimeError as exc:
        problems.append(str(exc))
        return {
            "ok": False,
            "problems": problems,
            "warnings": warnings,
            "installed_packages": installed_packages,
        }

    version = subprocess.run(
        prefix + ["Rscript", "--version"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if version.returncode != 0:
        problems.append(
            "Rscript is unavailable inside the Apptainer image: "
            + (
                version.stderr.strip()
                or version.stdout.strip()
                or f"exit {version.returncode}"
            )
        )
        return {
            "ok": False,
            "problems": problems,
            "warnings": warnings,
            "installed_packages": installed_packages,
        }

    expression = (
        "pkgs <- commandArgs(TRUE); "
        "for (p in pkgs) cat("
        "p, '\\t', "
        "if(requireNamespace(p, quietly=TRUE)) "
        "as.character(packageVersion(p)) else 'MISSING', "
        "'\\n', sep='')"
    )
    package_check = subprocess.run(
        prefix
        + [
            "Rscript",
            "--vanilla",
            "-e",
            expression,
            *required_r_packages,
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    if package_check.returncode != 0:
        problems.append(
            "Could not inspect R packages in the container: "
            + (
                package_check.stderr.strip()
                or package_check.stdout.strip()
            )
        )
    else:
        for line in package_check.stdout.splitlines():
            if "\t" not in line:
                continue
            package, version_text = line.split("\t", 1)
            installed_packages[package] = version_text
            if version_text == "MISSING":
                problems.append(
                    "Required R package is missing: "
                    f"{package}"
                )

    free_bytes = shutil.disk_usage(settings.workspace.parent).free
    if free_bytes < 2 * 1024**3:
        warnings.append(
            "Less than 2 GiB of free disk space is available."
        )

    return {
        "ok": not problems,
        "problems": problems,
        "warnings": warnings,
        "installed_packages": installed_packages,
        "r_runtime": "apptainer",
        "apptainer_image": str(settings.apptainer_image),
        "slurm_required": require_slurm,
    }
