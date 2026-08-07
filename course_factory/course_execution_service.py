from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from pydantic import ValidationError

from .apptainer_tasks import build_apptainer_r_task
from .course_execution_models import (
    CourseExecutionReport,
    CourseScriptExecution,
    ExecutedOutput,
    ScriptExecutionAttempt,
)
from .course_request_models import (
    CourseExecutor,
    CreateCourseRequest,
)
from .hpc_settings import HPCSettings
from .llm_backend import LLMBackend
from .local_runtime import LocalRuntimeBackend
from .r_code_models import (
    RCodeLLMResponse,
    RScriptArtifact,
)
from .r_code_validator import RCodeValidator
from .runtime_models import (
    ResourceRequest,
    RuntimeKind,
    RuntimeResult,
)
from .runtime_router import RuntimeRouter
from .slurm_runtime import SlurmRuntimeBackend
from .workspace_manager import WorkspaceManager


REPAIR_SCHEMA = '''{
  "code": "complete corrected R script",
  "expected_outputs": ["all concrete relative output paths required by this script"],
  "knowledge_ids": []
}'''


class CourseExecutionService:
    def __init__(
        self,
        *,
        settings: HPCSettings,
        workspace: WorkspaceManager,
        router: RuntimeRouter | None = None,
        backend: LLMBackend | None = None,
        max_repair_attempts: int | None = None,
    ) -> None:
        self.settings = settings
        self.workspace = workspace
        self.backend = backend
        self.max_repair_attempts = (
            settings.r_execution_repair_attempts
            if max_repair_attempts is None
            else max_repair_attempts
        )
        if self.max_repair_attempts < 0:
            raise ValueError(
                "max_repair_attempts cannot be negative"
            )

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

    @staticmethod
    def _write_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

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

    @staticmethod
    def _check_expected_outputs(
        output_dir: Path,
        expected_outputs: tuple[str, ...],
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        found = []
        missing = []

        for expected in expected_outputs:
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

        return tuple(found), tuple(missing)

    @staticmethod
    def _reset_output_directory(
        task_directory: Path,
    ) -> Path:
        output_dir = task_directory / "output"
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    @staticmethod
    def _diagnostic_text(
        *,
        runtime_result: RuntimeResult,
        missing_outputs: tuple[str, ...],
        produced_outputs: tuple[ExecutedOutput, ...],
    ) -> str:
        produced = [
            output.relative_path
            for output in produced_outputs
        ]
        return (
            f"Exit code: {runtime_result.return_code}\n\n"
            f"STDOUT:\n{runtime_result.stdout}\n\n"
            f"STDERR:\n{runtime_result.stderr}\n\n"
            f"Missing required outputs: "
            f"{list(missing_outputs)!r}\n"
            f"Produced outputs: {produced!r}"
        )

    @staticmethod
    def _repair_validation_errors(
        error: Exception,
    ) -> tuple[str, ...]:
        if isinstance(error, ValidationError):
            return tuple(
                (
                    ".".join(
                        str(part)
                        for part in item["loc"]
                    )
                    + ": "
                    + item["msg"]
                )
                for item in error.errors()
            )
        return (
            f"{type(error).__name__}: {error}",
        )

    def _repair_script(
        self,
        *,
        script: RScriptArtifact,
        current_code: str,
        runtime_result: RuntimeResult,
        missing_outputs: tuple[str, ...],
        produced_outputs: tuple[ExecutedOutput, ...],
        task_directory: Path,
        repair_number: int,
    ) -> tuple[str | None, Path, Path | None, tuple[str, ...]]:
        trace_dir = (
            task_directory
            / "repair"
            / f"attempt_{repair_number:02d}"
        )
        request_path = trace_dir / "request.json"
        response_path = trace_dir / "response.json"

        system = (
            "You are repairing an R teaching script that failed in a "
            "non-interactive Apptainer execution. Return the complete "
            "corrected script as JSON. Preserve the educational intent. "
            "Use only approved packages. Do not install packages, access "
            "the network, call system commands, use absolute paths, call "
            "setwd(), or require user interaction. Every required output "
            "must be written to its exact relative path. Create parent "
            "directories with dir.create(..., recursive=TRUE, "
            "showWarnings=FALSE). For ggplot2 figures, use ggsave with "
            "the exact required path. Do not save into plots/ when the "
            "required path begins with figures/."
        )
        user = (
            f"TASK ID: {script.task_id}\n"
            f"LESSON ID: {script.lesson_id}\n"
            f"APPROVED PACKAGES: "
            f"{list(script.required_packages)!r}\n"
            f"REQUIRED OUTPUTS: "
            f"{list(script.expected_outputs)!r}\n\n"
            f"CURRENT SCRIPT:\n{current_code}\n\n"
            "EXECUTION DIAGNOSTICS:\n"
            + self._diagnostic_text(
                runtime_result=runtime_result,
                missing_outputs=missing_outputs,
                produced_outputs=produced_outputs,
            )
        )

        self._write_json(
            request_path,
            {
                "system": system,
                "user": user,
                "schema_hint": REPAIR_SCHEMA,
            },
        )

        if self.backend is None:
            return (
                None,
                request_path,
                None,
                (
                    "No LLM backend is configured for repair.",
                ),
            )

        try:
            raw = self.backend.generate_json(
                system=system,
                user=user,
                schema_hint=REPAIR_SCHEMA,
            )
            self._write_json(response_path, raw)

            response = RCodeLLMResponse.model_validate(raw)
            if (
                set(response.expected_outputs)
                != set(script.expected_outputs)
            ):
                raise ValueError(
                    "Repaired expected_outputs must exactly match "
                    f"{list(script.expected_outputs)!r}; received "
                    f"{list(response.expected_outputs)!r}."
                )

            unknown_knowledge = (
                set(response.knowledge_ids)
                - set(script.knowledge_ids)
            )
            if unknown_knowledge:
                raise ValueError(
                    "Repaired script contains unknown knowledge IDs: "
                    + ", ".join(
                        sorted(unknown_knowledge)
                    )
                )

            validation = RCodeValidator(
                allowed_packages=script.required_packages
            ).validate(
                response.code,
                script.expected_outputs,
            )
            errors = tuple(
                (
                    f"{issue.rule}: {issue.message}"
                )
                for issue in validation.issues
                if issue.severity == "error"
            )
            warnings = tuple(
                issue
                for issue in validation.issues
                if issue.severity == "warning"
            )
            if errors:
                raise ValueError("; ".join(errors))

            # Output-path references are warnings in the general
            # validator, but they are mandatory for a repaired script.
            missing_references = tuple(
                issue.message
                for issue in warnings
                if issue.rule == "output_not_referenced"
            )
            if missing_references:
                raise ValueError(
                    "; ".join(missing_references)
                )

            return (
                response.code,
                request_path,
                response_path,
                (),
            )
        except Exception as exc:
            return (
                None,
                request_path,
                (
                    response_path
                    if response_path.exists()
                    else None
                ),
                self._repair_validation_errors(exc),
            )

    def _run_script_once(
        self,
        *,
        script: RScriptArtifact,
        code_path: Path,
        task_directory: Path,
        image: Path,
        runtime: RuntimeKind,
        resources: ResourceRequest,
    ) -> tuple[
        RuntimeResult,
        tuple[str, ...],
        tuple[str, ...],
        tuple[ExecutedOutput, ...],
    ]:
        shutil.copy2(
            code_path,
            task_directory / "script.R",
        )
        output_dir = self._reset_output_directory(
            task_directory
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
        outputs = self._collect_outputs(output_dir)
        found, missing = self._check_expected_outputs(
            output_dir,
            script.expected_outputs,
        )
        return runtime_result, found, missing, outputs

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
        repaired_tasks = []
        total_repairs = 0

        for script in scripts:
            task_directory = self.workspace.task_directory(
                job_id=job_id,
                task_id=script.task_id,
            )
            source = Path(script.relative_path)
            if not source.is_file():
                raise FileNotFoundError(source)

            current_code_path = source
            attempts = []
            final_runtime = None
            final_found = ()
            final_missing = ()
            final_outputs = ()
            repair_count = 0

            max_executions = (
                1 + self.max_repair_attempts
            )

            for execution_number in range(
                1,
                max_executions + 1,
            ):
                (
                    runtime_result,
                    found,
                    missing,
                    outputs,
                ) = self._run_script_once(
                    script=script,
                    code_path=current_code_path,
                    task_directory=task_directory,
                    image=image,
                    runtime=runtime,
                    resources=resources,
                )

                final_runtime = runtime_result
                final_found = found
                final_missing = missing
                final_outputs = outputs
                succeeded = (
                    runtime_result.succeeded
                    and not missing
                )

                attempt = ScriptExecutionAttempt(
                    attempt=execution_number,
                    repaired=execution_number > 1,
                    script_path=str(current_code_path),
                    runtime_result=runtime_result,
                    expected_outputs_found=found,
                    expected_outputs_missing=missing,
                )

                if succeeded:
                    attempts.append(attempt)
                    break

                if (
                    execution_number
                    >= max_executions
                ):
                    attempts.append(attempt)
                    break

                repaired_code, request_path, response_path, errors = (
                    self._repair_script(
                        script=script,
                        current_code=(
                            current_code_path.read_text(
                                encoding="utf-8"
                            )
                        ),
                        runtime_result=runtime_result,
                        missing_outputs=missing,
                        produced_outputs=outputs,
                        task_directory=task_directory,
                        repair_number=execution_number,
                    )
                )
                attempts.append(
                    attempt.model_copy(
                        update={
                            "repair_request_path": str(
                                request_path
                            ),
                            "repair_response_path": (
                                str(response_path)
                                if response_path
                                else None
                            ),
                            "repair_validation_errors": errors,
                        }
                    )
                )

                if repaired_code is None:
                    break

                repair_count += 1
                total_repairs += 1
                repaired_path = (
                    task_directory
                    / "repair"
                    / f"repaired_{repair_count:02d}.R"
                )
                repaired_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                repaired_path.write_text(
                    repaired_code.rstrip() + "\n",
                    encoding="utf-8",
                )
                current_code_path = repaired_path

            assert final_runtime is not None

            result = CourseScriptExecution(
                task_id=script.task_id,
                lesson_id=script.lesson_id,
                runtime_result=final_runtime,
                expected_outputs_found=final_found,
                expected_outputs_missing=final_missing,
                outputs=final_outputs,
                attempts=tuple(attempts),
                final_script_path=str(
                    current_code_path
                ),
                repair_count=repair_count,
            )
            results.append(result)

            if result.succeeded:
                successful.append(script.task_id)
                if repair_count:
                    repaired_tasks.append(script.task_id)
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
            repair_attempt_count=total_repairs,
            repaired_task_ids=tuple(repaired_tasks),
        )
