from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

from .runtime_backend import RuntimeBackend
from .runtime_models import RuntimeKind, RuntimeResult, RuntimeTask


class LocalRuntimeBackend(RuntimeBackend):
    def execute(self, task: RuntimeTask) -> RuntimeResult:
        workdir = Path(task.working_directory)
        if not workdir.is_dir():
            raise NotADirectoryError(workdir)

        environment = os.environ.copy()
        environment.update(task.environment)

        started = time.perf_counter()
        process = subprocess.run(
            list(task.command),
            cwd=workdir,
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        duration = time.perf_counter() - started

        if task.stdout_path:
            Path(task.stdout_path).write_text(
                process.stdout,
                encoding="utf-8",
            )
        if task.stderr_path:
            Path(task.stderr_path).write_text(
                process.stderr,
                encoding="utf-8",
            )

        return RuntimeResult(
            task_id=task.task_id,
            runtime=RuntimeKind.LOCAL,
            return_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
            submitted=True,
            completed=True,
            duration_seconds=duration,
        )
