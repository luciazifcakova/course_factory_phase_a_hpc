from __future__ import annotations

from pathlib import Path
import shlex
import shutil
import subprocess
import time

from .runtime_backend import RuntimeBackend
from .runtime_models import RuntimeKind, RuntimeResult, RuntimeTask


class SlurmRuntimeBackend(RuntimeBackend):
    '''
    Marker-file SLURM backend.

    This implementation deliberately does not call sacct. The submitted
    wrapper always writes an exit-code file and then atomically creates a
    completion marker. squeue is used only to detect jobs that disappear
    without producing their marker.
    '''

    def __init__(
        self,
        *,
        sbatch: str = "sbatch",
        squeue: str = "squeue",
        scancel: str = "scancel",
        poll_interval_seconds: float = 10.0,
        wait_timeout_seconds: float = 7200.0,
    ) -> None:
        self.sbatch = sbatch
        self.squeue = squeue
        self.scancel = scancel
        self.poll_interval_seconds = poll_interval_seconds
        self.wait_timeout_seconds = wait_timeout_seconds

    def validate(self) -> None:
        for executable in (
            self.sbatch,
            self.squeue,
            self.scancel,
        ):
            if shutil.which(executable) is None:
                raise RuntimeError(
                    f"Missing SLURM executable: {executable}"
                )

    def _paths(
        self,
        task: RuntimeTask,
    ) -> tuple[Path, Path, Path]:
        workdir = Path(task.working_directory)
        control = workdir / ".course_factory"
        control.mkdir(parents=True, exist_ok=True)
        exit_path = control / f"{task.task_id}.exitcode"
        finished_path = control / f"{task.task_id}.finished"
        script_path = control / f"{task.task_id}.sbatch"
        return script_path, exit_path, finished_path

    def _script_text(
        self,
        task: RuntimeTask,
        *,
        exit_path: Path | None = None,
        finished_path: Path | None = None,
    ) -> str:
        resources = task.resources
        if exit_path is None or finished_path is None:
            _, default_exit, default_finished = self._paths(task)
            exit_path = exit_path or default_exit
            finished_path = finished_path or default_finished

        stdout_path = Path(
            task.stdout_path
            or Path(task.working_directory)
            / "logs"
            / f"{task.task_id}-%j.out"
        )
        stderr_path = Path(
            task.stderr_path
            or Path(task.working_directory)
            / "logs"
            / f"{task.task_id}-%j.err"
        )
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "#!/usr/bin/env bash",
            f"#SBATCH --job-name={task.task_id}",
            f"#SBATCH --cpus-per-task={resources.cpus}",
            f"#SBATCH --mem={resources.memory_gb}G",
            f"#SBATCH --time={resources.time_minutes}",
            f"#SBATCH --output={stdout_path}",
            f"#SBATCH --error={stderr_path}",
        ]
        if resources.partition:
            lines.append(
                f"#SBATCH --partition={resources.partition}"
            )
        if resources.gpus:
            lines.append(
                f"#SBATCH --gres=gpu:{resources.gpus}"
            )

        lines.extend(
            [
                "set -uo pipefail",
                f"rm -f {shlex.quote(str(exit_path))} "
                f"{shlex.quote(str(finished_path))}",
                (
                    "finish_course_factory_job() { "
                    "code=$?; "
                    f"printf '%s\\n' \"$code\" > "
                    f"{shlex.quote(str(exit_path))}; "
                    f"touch {shlex.quote(str(finished_path))}; "
                    "exit \"$code\"; "
                    "}"
                ),
                "trap finish_course_factory_job EXIT",
            ]
        )

        for key, value in sorted(task.environment.items()):
            lines.append(
                f"export {key}={shlex.quote(value)}"
            )

        lines.append(
            f"cd {shlex.quote(task.working_directory)}"
        )
        lines.append(
            " ".join(
                shlex.quote(part)
                for part in task.command
            )
        )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _read_text(path: str | None) -> str:
        if path and Path(path).is_file():
            return Path(path).read_text(
                encoding="utf-8",
                errors="replace",
            )
        return ""

    def execute(self, task: RuntimeTask) -> RuntimeResult:
        self.validate()
        workdir = Path(task.working_directory)
        if not workdir.is_dir():
            raise NotADirectoryError(workdir)

        script_path, exit_path, finished_path = self._paths(task)
        exit_path.unlink(missing_ok=True)
        finished_path.unlink(missing_ok=True)

        script_path.write_text(
            self._script_text(
                task,
                exit_path=exit_path,
                finished_path=finished_path,
            ),
            encoding="utf-8",
        )

        started = time.perf_counter()
        submit = subprocess.run(
            [
                self.sbatch,
                "--parsable",
                str(script_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if submit.returncode != 0:
            return RuntimeResult(
                task_id=task.task_id,
                runtime=RuntimeKind.SLURM,
                return_code=submit.returncode,
                stdout=submit.stdout,
                stderr=submit.stderr,
                submitted=False,
                completed=False,
                duration_seconds=(
                    time.perf_counter() - started
                ),
            )

        job_id = submit.stdout.strip().split(";")[0]
        deadline = (
            time.monotonic() + self.wait_timeout_seconds
        )

        while time.monotonic() < deadline:
            if finished_path.is_file() and exit_path.is_file():
                try:
                    return_code = int(
                        exit_path.read_text(
                            encoding="utf-8"
                        ).strip()
                    )
                except ValueError:
                    return_code = 125

                return RuntimeResult(
                    task_id=task.task_id,
                    runtime=RuntimeKind.SLURM,
                    return_code=return_code,
                    stdout=self._read_text(task.stdout_path),
                    stderr=self._read_text(task.stderr_path),
                    external_job_id=job_id,
                    submitted=True,
                    completed=True,
                    duration_seconds=(
                        time.perf_counter() - started
                    ),
                )

            queue = subprocess.run(
                [
                    self.squeue,
                    "-h",
                    "-j",
                    job_id,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            if (
                queue.returncode == 0
                and not queue.stdout.strip()
                and not finished_path.exists()
            ):
                return RuntimeResult(
                    task_id=task.task_id,
                    runtime=RuntimeKind.SLURM,
                    return_code=125,
                    stdout=self._read_text(task.stdout_path),
                    stderr=(
                        self._read_text(task.stderr_path)
                        + (
                            "\nSLURM job disappeared from squeue "
                            "without producing a completion marker."
                        )
                    ).strip(),
                    external_job_id=job_id,
                    submitted=True,
                    completed=True,
                    duration_seconds=(
                        time.perf_counter() - started
                    ),
                )

            time.sleep(self.poll_interval_seconds)

        subprocess.run(
            [self.scancel, job_id],
            capture_output=True,
            text=True,
            check=False,
        )

        return RuntimeResult(
            task_id=task.task_id,
            runtime=RuntimeKind.SLURM,
            return_code=124,
            stdout=self._read_text(task.stdout_path),
            stderr=(
                self._read_text(task.stderr_path)
                + "\nSLURM supervisor timeout; job cancelled."
            ).strip(),
            external_job_id=job_id,
            submitted=True,
            completed=True,
            duration_seconds=time.perf_counter() - started,
        )
