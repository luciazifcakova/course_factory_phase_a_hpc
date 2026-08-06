from __future__ import annotations

import hashlib
from pathlib import Path
import shutil

from .apptainer_tasks import build_apptainer_r_task
from .course_execution_models import (
    CourseExecutionReport,
    CourseScriptExecution,
    ExecutedOutput,
)
from .course_request_models import (
    CourseExecutor,
    CreateCourseRequest,
)
from .hpc_settings import HPCSettings
from .local_runtime import LocalRuntimeBackend
from .r_code_models import RScriptArtifact
from .runtime_models import ResourceRequest, RuntimeKind
from .runtime_router import RuntimeRouter
from .slurm_runtime import SlurmRuntimeBackend
from .workspace_manager import WorkspaceManager


class CourseExecutionService:
    def __init__(
        self,
        *,
        settings: HPCSettings,
        workspace: WorkspaceManager,
        router: RuntimeRouter | None = None,
    ) -> None:
        self.settings = settings
        self.workspace = workspace
        self.router = router or RuntimeRouter(
            local=LocalRuntimeBackend(),
            slurm=SlurmRuntimeBackend(
                poll_interval_seconds=(
                    settings.slurm_poll_seconds
                ),
                wait_timeout_seconds=(
                    settings.slurm_wait_seconds
                ),
            ),
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(
                lambda: handle.read(1024 * 1024),
                b"",
            ):
                digest.update(block)
        return digest.hexdigest()

    @classmethod
    def _collect_outputs(
        cls,
        output_dir: Path,
    ) -> tuple[ExecutedOutput, ...]:
        if not output_dir.is_dir():
            return ()

        outputs = []
        for path in sorted(output_dir.rglob("*")):
            if not path.is_file():
                continue
            outputs.append(
                ExecutedOutput(
                    relative_path=path.relative_to(
                        output_dir
                    ).as_posix(),
                    absolute_path=str(path),
                    size_bytes=path.stat().st_size,
                    sha256=cls._sha256(path),
                )
            )
        return tuple(outputs)

    def execute(
        self,
        *,
        job_id: str,
        scripts: tuple[RScriptArtifact, ...],
        request: CreateCourseRequest,
    ) -> CourseExecutionReport:
        if request.executor is CourseExecutor.NONE:
            raise ValueError(
                "Execution requires local or slurm executor."
            )

        image = self.settings.apptainer_image
        if image is None:
            raise RuntimeError(
                "APPTAINER_IMAGE is not configured."
            )
        if not image.is_file():
            raise FileNotFoundError(image)

        runtime = (
            RuntimeKind.SLURM
            if request.executor is CourseExecutor.SLURM
            else RuntimeKind.LOCAL
        )
        resources = ResourceRequest(
            cpus=(
                request.execution_cpus
                or self.settings.slurm_cpus
            ),
            memory_gb=(
                request.execution_memory_gb
                or self.settings.slurm_memory_gb
            ),
            time_minutes=(
                request.execution_time_minutes
                or self.settings.slurm_time_minutes
            ),
            partition=(
                request.execution_partition
                or self.settings.slurm_partition
            ),
        )

        results = []
        successful = []
        failed = []

        for script in scripts:
            task_directory = self.workspace.task_directory(
                job_id=job_id,
                task_id=script.task_id,
            )
            source = Path(script.relative_path)
            if not source.is_file():
                raise FileNotFoundError(source)

            shutil.copy2(
                source,
                task_directory / "script.R",
            )

            task = build_apptainer_r_task(
                task_id=script.task_id,
                task_directory=task_directory,
                image=image,
                runtime=runtime,
                resources=resources,
                timeout_seconds=(
                    self.settings.local_timeout_seconds
                ),
            )
            runtime_result = self.router.execute(task)

            output_dir = task_directory / "output"
            found = []
            missing = []
            for expected in script.expected_outputs:
                relative = Path(expected)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                ):
                    raise ValueError(
                        "Unsafe expected output path: "
                        f"{expected}"
                    )
                if (output_dir / relative).is_file():
                    found.append(relative.as_posix())
                else:
                    missing.append(relative.as_posix())

            result = CourseScriptExecution(
                task_id=script.task_id,
                lesson_id=script.lesson_id,
                runtime_result=runtime_result,
                expected_outputs_found=tuple(found),
                expected_outputs_missing=tuple(missing),
                outputs=self._collect_outputs(output_dir),
            )
            results.append(result)

            if result.succeeded:
                successful.append(script.task_id)
            else:
                failed.append(script.task_id)

        return CourseExecutionReport(
            executor=runtime,
            results=tuple(results),
            successful_task_ids=tuple(successful),
            failed_task_ids=tuple(failed),
            output_count=sum(
                len(result.outputs)
                for result in results
            ),
        )
