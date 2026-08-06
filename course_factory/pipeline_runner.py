from __future__ import annotations

import json
from pathlib import Path

from .course_planner_agent import CoursePlannerAgent
from .course_request_models import CreateCourseRequest
from .course_response_models import (
    CourseArtifact,
    CreateCourseResponse,
)
from .input_builder_agent import InputBuilderAgent
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
    ) -> None:
        self.backend = backend
        self.jobs = jobs

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
                status="completed",
                step="outline_complete",
                patch={
                    "course_specification": specification,
                    "course_outline": outline,
                    "artifacts": [
                        artifact.model_dump(mode="json")
                        for artifact in artifacts
                    ],
                },
                message="Course outline created successfully.",
            )

            return CreateCourseResponse(
                job_id=job_id,
                status="completed",
                current_step="outline_complete",
                job_directory=str(directory),
                artifacts=tuple(artifacts),
                message=(
                    "Course specification and outline were created. "
                    "Slides, R scripts and PowerPoint are added in "
                    "subsequent commits."
                ),
                metrics={
                    **input_result.metrics,
                    **planner_result.metrics,
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
