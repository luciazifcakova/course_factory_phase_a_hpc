from __future__ import annotations

import json
from pathlib import Path

from .course_planner_agent import CoursePlannerAgent
from .course_request_models import (
    CourseExecutor,
    CreateCourseRequest,
)
from .course_response_models import (
    CourseArtifact,
    CreateCourseResponse,
)
from .input_builder_agent import InputBuilderAgent
from .course_outline import CourseOutline
from .lesson_content_models import LessonContentSet
from .lesson_generation_agent import LessonGenerationAgent
from .lesson_markdown_renderer import LessonMarkdownRenderer
from .r_workflow_planner_agent import RWorkflowPlannerAgent
from .r_code_generation_agent import RCodeGenerationAgent
from .security_validator_agent import SecurityValidatorAgent
from .course_execution_service import CourseExecutionService
from .hpc_settings import HPCSettings
from .r_code_models import RScriptArtifact
from .job_context import JobContext
from .job_manager import JobManager
from .llm_backend import LLMBackend
from .types import AgentStatus


class PipelineRunner:
    '''
    Minimal end-to-end course pipeline.

    Commit 0001 deliberately stops after producing a validated course
    specification and course outline. Later commits can add retrieval,
    slides, R generation, execution and PowerPoint without changing the
    public CourseFactoryAPI.
    '''

    def __init__(
        self,
        *,
        backend: LLMBackend,
        jobs: JobManager,
        settings: HPCSettings,
        execution_service: CourseExecutionService | None = None,
    ) -> None:
        self.backend = backend
        self.jobs = jobs
        self.settings = settings
        self.markdown_renderer = LessonMarkdownRenderer()
        self.execution_service = (
            execution_service
            or CourseExecutionService(
                settings=settings,
                workspace=jobs.workspace,
            )
        )

    @staticmethod
    def _write_json(
        directory: Path,
        filename: str,
        payload: dict,
    ) -> CourseArtifact:
        path = directory / filename
        path.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return CourseArtifact(
            name=filename.removesuffix(".json"),
            path=str(path),
        )

    def run(
        self,
        *,
        job_id: str,
        request: CreateCourseRequest,
    ) -> CreateCourseResponse:
        directory = self.jobs.workspace.job_directory(job_id)
        context = JobContext.create(
            job_id=job_id,
            user_request=request.effective_prompt(),
            config={
                "output_formats": list(request.output_formats),
            },
        )
        artifacts: list[CourseArtifact] = []

        try:
            self.jobs.transition(
                job_id=job_id,
                status="running",
                step="input_builder",
                message="Normalizing the course request.",
            )
            input_result = InputBuilderAgent(
                self.backend
            ).run(context)

            if input_result.status is AgentStatus.BLOCKED:
                specification = input_result.outputs.get(
                    "course_specification",
                    {},
                )
                if isinstance(specification, dict):
                    artifacts.append(
                        self._write_json(
                            directory,
                            "course_specification.json",
                            specification,
                        )
                    )
                self.jobs.transition(
                    job_id=job_id,
                    status="blocked",
                    step="clarification",
                    patch={
                        "course_specification": specification,
                        "errors": list(input_result.errors),
                    },
                    message=(
                        input_result.errors[0]
                        if input_result.errors
                        else "Clarification is required."
                    ),
                    level="WARNING",
                )
                return CreateCourseResponse(
                    job_id=job_id,
                    status="blocked",
                    current_step="clarification",
                    job_directory=str(directory),
                    artifacts=tuple(artifacts),
                    message="The request requires clarification.",
                    errors=input_result.errors,
                )

            if input_result.status is not AgentStatus.SUCCESS:
                raise RuntimeError(
                    "; ".join(input_result.errors)
                    or "Input builder failed."
                )

            context = context.with_result(input_result)
            specification = context.state["course_specification"]
            artifacts.append(
                self._write_json(
                    directory,
                    "course_specification.json",
                    specification,
                )
            )
            self.jobs.transition(
                job_id=job_id,
                status="running",
                step="course_planner",
                patch={
                    "course_specification": specification,
                },
                message="Course specification created.",
            )

            # Commit 0001 plans without retrieval. The existing planner
            # already accepts an empty local knowledge result list.
            state = dict(context.state)
            state["local_knowledge_results"] = []
            context = context.model_copy(update={"state": state})

            planner_result = CoursePlannerAgent(
                self.backend
            ).run(context)
            if planner_result.status is not AgentStatus.SUCCESS:
                raise RuntimeError(
                    "; ".join(planner_result.errors)
                    or "Course planner failed."
                )

            context = context.with_result(planner_result)
            outline = context.state["course_outline"]
            artifacts.append(
                self._write_json(
                    directory,
                    "course_outline.json",
                    outline,
                )
            )

            self.jobs.transition(
                job_id=job_id,
                status="running",
                step="lesson_generation",
                patch={"course_outline": outline},
                message=(
                    "Course outline created; generating lesson content."
                ),
            )

            lesson_result = LessonGenerationAgent(
                self.backend
            ).run(context)
            if lesson_result.status is not AgentStatus.SUCCESS:
                raise RuntimeError(
                    "; ".join(lesson_result.errors)
                    or "Lesson generation failed."
                )

            context = context.with_result(lesson_result)
            lesson_content_raw = context.state["lesson_content"]
            artifacts.append(
                self._write_json(
                    directory,
                    "lesson_content.json",
                    lesson_content_raw,
                )
            )

            lesson_paths = self.markdown_renderer.export(
                outline=CourseOutline.model_validate(outline),
                content=LessonContentSet.model_validate(
                    lesson_content_raw
                ),
                output_directory=directory / "lessons",
            )
            artifacts.extend(
                CourseArtifact(
                    name=(
                        "lesson_index"
                        if path.name == "README.md"
                        else path.stem
                    ),
                    path=str(path),
                    content_type="text/markdown",
                )
                for path in lesson_paths
            )

            self.jobs.transition(
                job_id=job_id,
                status="running",
                step="r_workflow_planning",
                patch={"lesson_content": lesson_content_raw},
                message="Markdown lessons created; planning R teaching scripts.",
            )

            workflow_result = RWorkflowPlannerAgent().run(context)
            if workflow_result.status is not AgentStatus.SUCCESS:
                raise RuntimeError(
                    "; ".join(workflow_result.errors)
                    or "R workflow planning failed."
                )
            context = context.with_result(workflow_result)
            workflow_plan = context.state["workflow_plan"]
            artifacts.append(
                self._write_json(directory, "workflow_plan.json", workflow_plan)
            )

            self.jobs.transition(
                job_id=job_id,
                status="running",
                step="r_code_generation",
                patch={"workflow_plan": workflow_plan},
                message="Generating validated R teaching scripts.",
            )

            r_result = RCodeGenerationAgent(
                self.backend,
                output_dir=directory / "scripts",
                trace_dir=(
                    directory
                    / "llm"
                    / "r_code_generation"
                ),
                max_attempts=3,
            ).run(context)

            # Persist diagnostics even when the generation agent encounters
            # task-level failures. This makes failed local-model responses
            # inspectable from the job directory.
            generation_report = r_result.outputs.get(
                "r_code_generation_report"
            )
            if isinstance(generation_report, dict):
                artifacts.append(
                    self._write_json(
                        directory,
                        "r_code_generation_report.json",
                        generation_report,
                    )
                )

            if r_result.status is not AgentStatus.SUCCESS:
                raise RuntimeError(
                    "; ".join(r_result.errors)
                    or "R code generation failed."
                )

            context = context.with_result(r_result)
            generation_report = context.state[
                "r_code_generation_report"
            ]

            if generation_report.get("failed_task_ids"):
                raise RuntimeError(
                    "R code generation failed for tasks: "
                    + ", ".join(generation_report["failed_task_ids"])
                )

            self.jobs.transition(
                job_id=job_id,
                status="running",
                step="security_validation",
                patch={
                    "generated_r_scripts": context.state["generated_r_scripts"]
                },
                message="Security-validating generated R scripts.",
            )

            security_result = SecurityValidatorAgent().run(context)
            if security_result.status is not AgentStatus.SUCCESS:
                raise RuntimeError(
                    "; ".join(security_result.errors)
                    or "R security validation failed."
                )
            context = context.with_result(security_result)
            security_report = context.state["security_report"]
            artifacts.append(
                self._write_json(
                    directory,
                    "security_report.json",
                    security_report,
                )
            )
            if security_report.get("rejected_count", 0):
                raise RuntimeError(
                    f"Security validation rejected "
                    f"{security_report['rejected_count']} R script(s)."
                )

            for script in context.state["approved_r_scripts"]:
                path = Path(script["relative_path"])
                artifacts.append(
                    CourseArtifact(
                        name=path.stem,
                        path=str(path),
                        content_type="text/x-r-source",
                    )
                )

            execution_report = None
            execution_metrics = {}

            if request.executor is not CourseExecutor.NONE:
                self.jobs.transition(
                    job_id=job_id,
                    status="running",
                    step="r_execution",
                    patch={
                        "executor": request.executor.value,
                    },
                    message=(
                        "Executing approved R scripts through "
                        "Apptainer using "
                        f"{request.executor.value}."
                    ),
                )

                approved_scripts = tuple(
                    RScriptArtifact.model_validate(script)
                    for script
                    in context.state["approved_r_scripts"]
                )
                execution_report_model = (
                    self.execution_service.execute(
                        job_id=job_id,
                        scripts=approved_scripts,
                        request=request,
                    )
                )
                execution_report = (
                    execution_report_model.model_dump(
                        mode="json"
                    )
                )
                artifacts.append(
                    self._write_json(
                        directory,
                        "execution_report.json",
                        execution_report,
                    )
                )

                for result in execution_report_model.results:
                    for output in result.outputs:
                        suffix = Path(
                            output.relative_path
                        ).suffix.lower()
                        content_type = {
                            ".png": "image/png",
                            ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg",
                            ".csv": "text/csv",
                            ".tsv": "text/tab-separated-values",
                            ".json": "application/json",
                        }.get(
                            suffix,
                            "application/octet-stream",
                        )
                        artifacts.append(
                            CourseArtifact(
                                name=(
                                    f"{result.lesson_id}_"
                                    f"{Path(output.relative_path).stem}"
                                ),
                                path=output.absolute_path,
                                content_type=content_type,
                            )
                        )

                execution_metrics = {
                    "executed_r_scripts": len(
                        execution_report_model.results
                    ),
                    "successful_r_scripts": len(
                        execution_report_model.successful_task_ids
                    ),
                    "failed_r_scripts": len(
                        execution_report_model.failed_task_ids
                    ),
                    "execution_output_count": (
                        execution_report_model.output_count
                    ),
                }

                if not execution_report_model.succeeded:
                    details = []
                    for result in (
                        execution_report_model.results
                    ):
                        if result.succeeded:
                            continue
                        details.append(
                            f"{result.task_id}: "
                            f"exit="
                            f"{result.runtime_result.return_code}, "
                            f"missing="
                            f"{list(result.expected_outputs_missing)!r}"
                        )
                    raise RuntimeError(
                        "R execution failed: "
                        + "; ".join(details)
                    )

            final_step = (
                "r_execution_complete"
                if execution_report is not None
                else "r_scripts_complete"
            )
            artifact_payload = [
                artifact.model_dump(mode="json")
                for artifact in artifacts
            ]
            state_patch = {
                "course_specification": specification,
                "course_outline": outline,
                "lesson_content": lesson_content_raw,
                "workflow_plan": workflow_plan,
                "r_code_generation_report": generation_report,
                "security_report": security_report,
                "approved_r_scripts": (
                    context.state["approved_r_scripts"]
                ),
                "artifacts": artifact_payload,
            }
            if execution_report is not None:
                state_patch[
                    "execution_report"
                ] = execution_report

            self.jobs.transition(
                job_id=job_id,
                status="completed",
                step=final_step,
                patch=state_patch,
                message=(
                    "Course lessons, approved R scripts and "
                    "execution artifacts created successfully."
                    if execution_report is not None
                    else "Course lessons and security-approved "
                    "R scripts created successfully."
                ),
            )

            return CreateCourseResponse(
                job_id=job_id,
                status="completed",
                current_step=final_step,
                job_directory=str(directory),
                artifacts=tuple(artifacts),
                message=(
                    "Course specification, outline, Markdown "
                    "lessons, R scripts and executed outputs "
                    "were created."
                    if execution_report is not None
                    else "Course specification, outline, "
                    "Markdown lessons and security-approved "
                    "R teaching scripts were created."
                ),
                metrics={
                    **input_result.metrics,
                    **planner_result.metrics,
                    **lesson_result.metrics,
                    **workflow_result.metrics,
                    **r_result.metrics,
                    **security_result.metrics,
                    **execution_metrics,
                },
            )

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            self.jobs.transition(
                job_id=job_id,
                status="failed",
                step="failed",
                patch={"errors": [error]},
                message=error,
                level="ERROR",
            )
            return CreateCourseResponse(
                job_id=job_id,
                status="failed",
                current_step="failed",
                job_directory=str(directory),
                artifacts=tuple(artifacts),
                message="Course generation failed.",
                errors=(error,),
            )
