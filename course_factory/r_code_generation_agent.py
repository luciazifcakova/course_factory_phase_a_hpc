from __future__ import annotations

import json
from fnmatch import fnmatch
from pathlib import PurePosixPath
from pathlib import Path
import re

from pydantic import ValidationError

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .job_context import JobContext
from .lesson_content_models import LessonContentSet
from .llm_backend import LLMBackend
from .r_code_models import (
    RCodeGenerationAttempt,
    RCodeGenerationReport,
    RCodeLLMResponse,
    RScriptArtifact,
)
from .r_code_validator import RCodeValidator
from .r_prompt_builder import build_r_code_prompt
from .workflow_plan import TaskType, WorkflowPlan


class RCodeGenerationAgent(Agent):
    name = "r_code_generator"
    version = "1.2.0"
    capabilities = frozenset({"r_code_generation"})

    def __init__(
        self,
        backend: LLMBackend,
        *,
        output_dir: str | Path = "workspace/generated_r",
        trace_dir: str | Path | None = None,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")

        self.backend = backend
        self.output_dir = Path(output_dir)
        self.trace_dir = (
            Path(trace_dir)
            if trace_dir is not None
            else self.output_dir.parent / "llm" / "r_code_generation"
        )
        self.max_attempts = max_attempts

    @staticmethod
    def _safe_identifier(value: str) -> str:
        cleaned = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            value,
        ).strip("._")
        return cleaned or "task"

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

    @staticmethod
    def _required_outputs(
        plan: WorkflowPlan,
        code_task_id: str,
    ) -> tuple[str, ...]:
        outputs: list[str] = []
        for task in plan.tasks:
            if (
                code_task_id in task.depends_on
                and task.task_type
                in {
                    TaskType.FIGURE,
                    TaskType.TABLE,
                }
            ):
                outputs.extend(task.output_artifacts)
        return tuple(dict.fromkeys(outputs))


    @staticmethod
    def _validate_output_contracts(
        *,
        contracts: tuple[str, ...],
        concrete_outputs: tuple[str, ...],
    ) -> tuple[str, ...]:
        if not contracts:
            return concrete_outputs

        if not concrete_outputs:
            raise ValueError(
                "The LLM returned no concrete expected_outputs for "
                f"required contracts {list(contracts)!r}."
            )

        normalized_outputs = []
        for output in concrete_outputs:
            path = PurePosixPath(output)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(
                    f"Unsafe expected output path: {output!r}"
                )
            normalized_outputs.append(path.as_posix())

        unmatched_outputs = [
            output
            for output in normalized_outputs
            if not any(
                fnmatch(output, contract)
                for contract in contracts
            )
        ]
        if unmatched_outputs:
            raise ValueError(
                "LLM returned outputs outside the workflow contracts; "
                f"contracts={list(contracts)!r}, "
                f"outside={unmatched_outputs!r}"
            )

        missing_contracts = [
            contract
            for contract in contracts
            if not any(
                fnmatch(output, contract)
                for output in normalized_outputs
            )
        ]
        if missing_contracts:
            raise ValueError(
                "No generated output satisfies workflow contracts: "
                f"{missing_contracts!r}; returned="
                f"{normalized_outputs!r}"
            )

        return tuple(dict.fromkeys(normalized_outputs))

    @staticmethod
    def _validation_messages(
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
        return (f"{type(error).__name__}: {error}",)

    @staticmethod
    def _repair_user_prompt(
        *,
        original_user: str,
        previous_response: dict,
        errors: tuple[str, ...],
    ) -> str:
        return (
            original_user
            + "\n\nYour previous JSON response was invalid. "
            "Correct it and return the complete JSON object again.\n\n"
            "VALIDATION ERRORS:\n- "
            + "\n- ".join(errors)
            + "\n\nPREVIOUS RESPONSE:\n"
            + json.dumps(
                previous_response,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    def _save_progress(
        self,
        *,
        scripts: list[RScriptArtifact],
        failed: list[str],
        failure_reasons: dict[str, tuple[str, ...]],
        attempts: list[RCodeGenerationAttempt],
    ) -> None:
        self._write_json(
            self.output_dir.parent
            / "r_code_generation_progress.json",
            {
                "generated_scripts": [
                    script.model_dump(mode="json")
                    for script in scripts
                ],
                "failed_task_ids": failed,
                "failure_reasons": {
                    key: list(value)
                    for key, value in failure_reasons.items()
                },
                "attempts": [
                    attempt.model_dump(mode="json")
                    for attempt in attempts
                ],
            },
        )

    def run(self, context: JobContext) -> AgentResult:
        outline_raw = context.state.get("course_outline")
        plan_raw = context.state.get("workflow_plan")
        lesson_content_raw = context.state.get(
            "lesson_content"
        )

        if not isinstance(outline_raw, dict) or not isinstance(
            plan_raw,
            dict,
        ):
            return AgentResult.failed(
                agent_name=self.name,
                errors=(
                    "course_outline or workflow_plan is missing",
                ),
            )

        try:
            outline = CourseOutline.model_validate(
                outline_raw
            )
            plan = WorkflowPlan.model_validate(plan_raw)
            lesson_content = (
                LessonContentSet.model_validate(
                    lesson_content_raw
                )
                if isinstance(lesson_content_raw, dict)
                else None
            )

            lessons = {
                lesson.lesson_id: lesson
                for module in outline.modules
                for lesson in module.lessons
            }
            content_by_lesson = {
                lesson.lesson_id: lesson.model_dump(
                    mode="json"
                )
                for lesson in (
                    lesson_content.lessons
                    if lesson_content
                    else ()
                )
            }
            knowledge = context.state.get(
                "local_knowledge_results",
                [],
            )
            knowledge_list = (
                knowledge
                if isinstance(knowledge, list)
                else []
            )

            scripts: list[RScriptArtifact] = []
            failed: list[str] = []
            failure_reasons: dict[
                str,
                tuple[str, ...],
            ] = {}
            attempts: list[RCodeGenerationAttempt] = []

            self.output_dir.mkdir(
                parents=True,
                exist_ok=True,
            )
            self.trace_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            for task in plan.tasks:
                if task.task_type is not TaskType.R_SCRIPT:
                    continue

                lesson = lessons.get(task.lesson_id)
                if lesson is None:
                    failed.append(task.task_id)
                    failure_reasons[task.task_id] = (
                        "Unknown lesson_id",
                    )
                    self._save_progress(
                        scripts=scripts,
                        failed=failed,
                        failure_reasons=failure_reasons,
                        attempts=attempts,
                    )
                    continue

                required_outputs = self._required_outputs(
                    plan,
                    task.task_id,
                )
                system, original_user, schema = (
                    build_r_code_prompt(
                        lesson=lesson,
                        task=task,
                        knowledge=knowledge_list,
                        lesson_content=(
                            content_by_lesson.get(
                                task.lesson_id
                            )
                        ),
                        required_outputs=required_outputs,
                    )
                )

                task_trace_dir = (
                    self.trace_dir
                    / self._safe_identifier(task.task_id)
                )
                user_prompt = original_user
                final_errors: tuple[str, ...] = ()
                artifact: RScriptArtifact | None = None

                for attempt_number in range(
                    1,
                    self.max_attempts + 1,
                ):
                    request_path = (
                        task_trace_dir
                        / f"attempt_{attempt_number:02d}_request.json"
                    )
                    response_path = (
                        task_trace_dir
                        / f"attempt_{attempt_number:02d}_response.json"
                    )
                    self._write_json(
                        request_path,
                        {
                            "task_id": task.task_id,
                            "attempt": attempt_number,
                            "system": system,
                            "user": user_prompt,
                            "schema_hint": schema,
                        },
                    )

                    raw_response: dict = {}
                    try:
                        raw_response = (
                            self.backend.generate_json(
                                system=system,
                                user=user_prompt,
                                schema_hint=schema,
                            )
                        )
                        if not isinstance(
                            raw_response,
                            dict,
                        ):
                            raise TypeError(
                                "LLM backend returned a "
                                "non-object JSON value."
                            )

                        self._write_json(
                            response_path,
                            raw_response,
                        )

                        validated = (
                            RCodeLLMResponse.model_validate(
                                raw_response
                            )
                        )
                        returned_outputs = tuple(
                            validated.expected_outputs
                        )
                        expected_outputs = (
                            self._validate_output_contracts(
                                contracts=required_outputs,
                                concrete_outputs=returned_outputs,
                            )
                        )

                        allowed_knowledge_ids = set(
                            lesson.knowledge_ids
                        )
                        unknown_ids = (
                            set(validated.knowledge_ids)
                            - allowed_knowledge_ids
                        )
                        if unknown_ids:
                            raise ValueError(
                                "Unknown knowledge IDs: "
                                + ", ".join(
                                    sorted(unknown_ids)
                                )
                            )

                        validation = RCodeValidator(
                            allowed_packages=(
                                task.required_packages
                            )
                        ).validate(
                            validated.code,
                            expected_outputs,
                        )
                        if not validation.ok:
                            raise ValueError(
                                "; ".join(
                                    f"{issue.rule}: "
                                    f"{issue.message}"
                                    for issue
                                    in validation.issues
                                )
                            )

                        target = (
                            self.output_dir
                            / f"{task.lesson_id}.R"
                        )
                        target.write_text(
                            validated.code.rstrip()
                            + "\n",
                            encoding="utf-8",
                        )
                        artifact = RScriptArtifact(
                            task_id=task.task_id,
                            lesson_id=task.lesson_id,
                            relative_path=str(target),
                            code=validated.code,
                            required_packages=(
                                task.required_packages
                            ),
                            expected_outputs=(
                                expected_outputs
                            ),
                            knowledge_ids=(
                                validated.knowledge_ids
                            ),
                        )
                        attempts.append(
                            RCodeGenerationAttempt(
                                task_id=task.task_id,
                                attempt=attempt_number,
                                succeeded=True,
                                request_path=str(
                                    request_path
                                ),
                                response_path=str(
                                    response_path
                                ),
                            )
                        )
                        break

                    except Exception as exc:
                        final_errors = (
                            self._validation_messages(exc)
                        )
                        attempts.append(
                            RCodeGenerationAttempt(
                                task_id=task.task_id,
                                attempt=attempt_number,
                                succeeded=False,
                                request_path=str(
                                    request_path
                                ),
                                response_path=(
                                    str(response_path)
                                    if response_path.exists()
                                    else None
                                ),
                                validation_errors=(
                                    final_errors
                                ),
                            )
                        )

                        if (
                            attempt_number
                            < self.max_attempts
                        ):
                            user_prompt = (
                                self._repair_user_prompt(
                                    original_user=(
                                        original_user
                                    ),
                                    previous_response=(
                                        raw_response
                                    ),
                                    errors=final_errors,
                                )
                            )

                if artifact is not None:
                    scripts.append(artifact)
                else:
                    failed.append(task.task_id)
                    failure_reasons[
                        task.task_id
                    ] = final_errors or (
                        "R generation failed without "
                        "a diagnostic message.",
                    )

                self._save_progress(
                    scripts=scripts,
                    failed=failed,
                    failure_reasons=failure_reasons,
                    attempts=attempts,
                )

            report = RCodeGenerationReport(
                scripts=tuple(scripts),
                generated_count=len(scripts),
                failed_task_ids=tuple(failed),
                failure_reasons=failure_reasons,
                attempts=tuple(attempts),
            )
            return AgentResult.success(
                agent_name=self.name,
                outputs={
                    "r_code_generation_report": (
                        report.model_dump(
                            mode="json"
                        )
                    ),
                    "generated_r_scripts": [
                        script.model_dump(
                            mode="json"
                        )
                        for script in report.scripts
                    ],
                },
                metrics={
                    "generated_r_scripts": len(scripts),
                    "failed_r_tasks": len(failed),
                    "r_generation_attempts": len(
                        attempts
                    ),
                    "r_generation_retries": sum(
                        1
                        for attempt in attempts
                        if not attempt.succeeded
                    ),
                },
            )

        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(
                    f"{type(exc).__name__}: {exc}",
                ),
            )
