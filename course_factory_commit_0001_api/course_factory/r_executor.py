from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import os
import shutil
import subprocess
import time

from .artifact_collector import ArtifactCollector
from .execution_models import (
    ExecutionRequest,
    ExecutionRuntime,
    ScriptExecutionResult,
)


class ExecutionBackend(ABC):
    @abstractmethod
    def build_command(self, request: ExecutionRequest) -> tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def validate(self, request: ExecutionRequest) -> None:
        raise NotImplementedError


class LocalRBackend(ExecutionBackend):
    def __init__(self, rscript: str = "Rscript") -> None:
        self.rscript = rscript

    def validate(self, request: ExecutionRequest) -> None:
        if shutil.which(self.rscript) is None:
            raise RuntimeError(f"{self.rscript!r} is not available")

    def build_command(self, request: ExecutionRequest) -> tuple[str, ...]:
        return (self.rscript, request.script_path)


class ApptainerRBackend(ExecutionBackend):
    def __init__(
        self,
        apptainer: str = "apptainer",
        rscript: str = "Rscript",
    ) -> None:
        self.apptainer = apptainer
        self.rscript = rscript

    def validate(self, request: ExecutionRequest) -> None:
        if shutil.which(self.apptainer) is None:
            raise RuntimeError(f"{self.apptainer!r} is not available")
        image = Path(request.apptainer_image or "")
        if not image.is_file():
            raise FileNotFoundError(f"Apptainer image not found: {image}")

    def build_command(self, request: ExecutionRequest) -> tuple[str, ...]:
        workspace = Path(request.workspace).resolve()
        image = Path(request.apptainer_image or "").resolve()
        script = Path(request.script_path).resolve()

        try:
            relative_script = script.relative_to(workspace).as_posix()
        except ValueError as exc:
            raise ValueError(
                "script_path must be located inside workspace"
            ) from exc

        return (
            self.apptainer,
            "exec",
            "--cleanenv",
            "--containall",
            "--no-home",
            "--bind",
            f"{workspace}:/work",
            "--pwd",
            "/work",
            str(image),
            self.rscript,
            f"/work/{relative_script}",
        )


class RExecutor:
    def __init__(
        self,
        *,
        collector: ArtifactCollector | None = None,
        local_backend: ExecutionBackend | None = None,
        apptainer_backend: ExecutionBackend | None = None,
    ) -> None:
        self.collector = collector or ArtifactCollector()
        self.local_backend = local_backend or LocalRBackend()
        self.apptainer_backend = apptainer_backend or ApptainerRBackend()

    def _backend(self, runtime: ExecutionRuntime) -> ExecutionBackend:
        if runtime is ExecutionRuntime.LOCAL:
            return self.local_backend
        if runtime is ExecutionRuntime.APPTAINER:
            return self.apptainer_backend
        raise ValueError(f"Unsupported runtime: {runtime}")

    def execute(self, request: ExecutionRequest) -> ScriptExecutionResult:
        workspace = Path(request.workspace).resolve()
        script = Path(request.script_path).resolve()

        if not workspace.is_dir():
            raise NotADirectoryError(workspace)
        if not script.is_file():
            raise FileNotFoundError(script)

        backend = self._backend(request.runtime)
        backend.validate(request)
        command = backend.build_command(request)
        before = self.collector.snapshot(workspace)

        environment = os.environ.copy()
        environment.update(request.environment)

        started = time.perf_counter()
        timed_out = False
        try:
            process = subprocess.run(
                list(command),
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=request.timeout_seconds,
                env=environment,
                check=False,
            )
            exit_code = process.returncode
            stdout = process.stdout
            stderr = process.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode(errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode(errors="replace")

        duration = time.perf_counter() - started
        artifacts = self.collector.collect(
            workspace=workspace,
            task_id=request.task_id,
            before=before,
        )

        found: list[str] = []
        missing: list[str] = []
        for expected in request.expected_outputs:
            expected_path = Path(expected)
            if expected_path.is_absolute() or ".." in expected_path.parts:
                raise ValueError(f"Unsafe expected output path: {expected}")
            if (workspace / expected_path).is_file():
                found.append(expected_path.as_posix())
            else:
                missing.append(expected_path.as_posix())

        return ScriptExecutionResult(
            task_id=request.task_id,
            lesson_id=request.lesson_id,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            runtime=request.runtime,
            command=command,
            duration_seconds=duration,
            timed_out=timed_out,
            expected_outputs_found=tuple(found),
            expected_outputs_missing=tuple(missing),
            collected_artifacts=artifacts,
        )
