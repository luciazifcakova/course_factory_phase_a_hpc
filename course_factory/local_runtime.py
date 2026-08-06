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
        try:
            process = subprocess.run(
                list(task.command),
                cwd=workdir,
                capture_output=True,
                text=True,
                env=environment,
                check=False,
                timeout=task.timeout_seconds,
            )
            return_code = process.returncode
            stdout = process.stdout
            stderr = process.stderr
        except subprocess.TimeoutExpired as exc:
            return_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")
            stderr = (
                stderr + "\nLocal execution timed out."
            ).strip()

        duration = time.perf_counter() - started

        if task.stdout_path:
            Path(task.stdout_path).write_text(
                stdout,
                encoding="utf-8",
            )
        if task.stderr_path:
            Path(task.stderr_path).write_text(
                stderr,
                encoding="utf-8",
            )

        return RuntimeResult(
            task_id=task.task_id,
            runtime=RuntimeKind.LOCAL,
            return_code=return_code,
            stdout=stdout,
            stderr=stderr,
            submitted=True,
            completed=True,
            duration_seconds=duration,
        )
