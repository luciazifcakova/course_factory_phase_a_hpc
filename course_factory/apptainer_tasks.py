from __future__ import annotations

from pathlib import Path

from .runtime_models import (
    ResourceRequest,
    RuntimeKind,
    RuntimeTask,
)


def build_apptainer_r_task(
    *,
    task_id: str,
    task_directory: str | Path,
    image: str | Path,
    runtime: RuntimeKind,
    resources: ResourceRequest,
) -> RuntimeTask:
    task_directory = Path(task_directory).resolve()
    image = Path(image).expanduser().resolve()
    script = task_directory / "script.R"

    if not script.is_file():
        raise FileNotFoundError(script)
    if not image.is_file():
        raise FileNotFoundError(image)

    command = (
        "apptainer",
        "exec",
        "--cleanenv",
        "--containall",
        "--no-home",
        "--net",
        "--network",
        "none",
        "--bind",
        f"{task_directory}:/job",
        "--pwd",
        "/job/output",
        str(image),
        "Rscript",
        "--vanilla",
        "/job/script.R",
    )

    return RuntimeTask(
        task_id=task_id,
        command=command,
        working_directory=str(task_directory),
        resources=resources,
        runtime=runtime,
        stdout_path=str(
            task_directory / "logs" / "stdout.log"
        ),
        stderr_path=str(
            task_directory / "logs" / "stderr.log"
        ),
    )
