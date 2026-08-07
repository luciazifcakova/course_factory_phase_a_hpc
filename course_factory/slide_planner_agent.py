from __future__ import annotations

import json
from pathlib import Path

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .job_artifacts import ArtifactManifest
from .job_context import JobContext
from .lesson_content_models import (
    LessonContentSet,
)
from .llm_backend import (
    LLMBackend,
    StructuredOutputError,
    ensure_structured_backend,
)
from .slide_models import (
    CourseSlidePlan,
    LessonSlidePlan,
    SlideGenerationAttempt,
)


class SlidePlannerAgent(Agent):
    name = "slide_planner"
    version = "1.0.0"
    capabilities = frozenset(
        {"slide_planning"}
    )

    def __init__(
        self,
        backend: LLMBackend,
        *,
        trace_dir: str | Path,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least one"
            )
        self.backend = ensure_structured_backend(
            backend
        )
        self.trace_dir = Path(trace_dir)
        self.max_attempts = max_attempts

    @staticmethod
    def _write_json(
        path: Path,
        payload,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
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
    def _errors(exc: Exception) -> tuple[str, ...]:
        if isinstance(
            exc,
            StructuredOutputError,
        ):
            return (str(exc),)
        return (
            f"{type(exc).__name__}: {exc}",
        )

    @staticmethod
    def _validate_plan_artifacts(
        *,
        plan: LessonSlidePlan,
        lesson_manifest,
    ) -> None:
        allowed_figures = {
            item.relative_path
            for item in lesson_manifest.figures
        }
        allowed_code = (
            lesson_manifest.script.relative_path
            if lesson_manifest.script is not None
            else None
        )

        for slide in plan.slides:
            unknown_figures = (
                set(slide.figure_artifacts)
                - allowed_figures
            )
            if unknown_figures:
                raise ValueError(
                    f"slide {slide.slide_id!r} references "
                    "figures outside the lesson manifest: "
                    + ", ".join(
                        sorted(unknown_figures)
                    )
                )

            if (
                slide.code_artifact is not None
                and slide.code_artifact
                != allowed_code
            ):
                raise ValueError(
                    f"slide {slide.slide_id!r} references "
                    "an unknown code artifact"
                )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are planning teaching slides for one R lesson. "
            "Return data matching the supplied JSON schema exactly. "
            "Create a compact pedagogical sequence, normally 3-8 slides. "
            "Use layouts only from the schema. Do not write final bullet "
            "content yet; the purpose field describes what each slide "
            "should teach. You may reference ONLY figure and code paths "
            "listed in AVAILABLE ARTIFACTS. Never invent filenames. "
            "Prefer PNG figures for visual slides. Use at most two "
            "figures on one slide. Include a title/overview slide and "
            "a summary or exercise when pedagogically useful."
        )

    @staticmethod
    def _user_prompt(
        *,
        lesson,
        lesson_content,
        lesson_manifest,
    ) -> str:
        available_figures = [
            figure.relative_path
            for figure
            in lesson_manifest.figures
        ]
        return (
            "LESSON PLAN:\n"
            f"{lesson.model_dump_json(indent=2)}\n\n"
            "LESSON CONTENT:\n"
            f"{lesson_content.model_dump_json(indent=2)}\n\n"
            "AVAILABLE ARTIFACTS:\n"
            + json.dumps(
                {
                    "figures": available_figures,
                    "code": (
                        lesson_manifest
                        .script.relative_path
                        if lesson_manifest.script
                        is not None
                        else None
                    ),
                },
                indent=2,
            )
            + "\n\nRULE: every slide lesson_id must be "
            f"{lesson.lesson_id!r}. Use globally descriptive "
            "slide IDs prefixed with the lesson ID, for example "
            f"{lesson.lesson_id}-S01."
        )

    def run(
        self,
        context: JobContext,
    ) -> AgentResult:
        outline_raw = context.state.get(
            "course_outline"
        )
        content_raw = context.state.get(
            "lesson_content"
        )
        manifest_raw = context.state.get(
            "artifact_manifest"
        )

        if not isinstance(outline_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_outline is missing",),
            )
        if not isinstance(content_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("lesson_content is missing",),
            )
        if not isinstance(manifest_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("artifact_manifest is missing",),
            )

        try:
            outline = CourseOutline.model_validate(
                outline_raw
            )
            content = (
                LessonContentSet.model_validate(
                    content_raw
                )
            )
            manifest = (
                ArtifactManifest.model_validate(
                    manifest_raw
                )
            )

            content_by_id = {
                lesson.lesson_id: lesson
                for lesson in content.lessons
            }
            manifest_by_id = {
                lesson.lesson_id: lesson
                for lesson in manifest.lessons
            }

            plans = []
            attempts = []
            total_attempts = 0

            for module in outline.modules:
                for lesson in module.lessons:
                    lesson_content = content_by_id[
                        lesson.lesson_id
                    ]
                    lesson_manifest = manifest_by_id[
                        lesson.lesson_id
                    ]

                    system = self._system_prompt()
                    original_user = self._user_prompt(
                        lesson=lesson,
                        lesson_content=lesson_content,
                        lesson_manifest=(
                            lesson_manifest
                        ),
                    )
                    user = original_user
                    final_errors = ()

                    for attempt in range(
                        1,
                        self.max_attempts + 1,
                    ):
                        total_attempts += 1
                        lesson_trace = (
                            self.trace_dir
                            / lesson.lesson_id
                        )
                        request_path = (
                            lesson_trace
                            / (
                                f"attempt_{attempt:02d}"
                                "_request.json"
                            )
                        )
                        response_path = (
                            lesson_trace
                            / (
                                f"attempt_{attempt:02d}"
                                "_response.json"
                            )
                        )
                        self._write_json(
                            request_path,
                            {
                                "system": system,
                                "user": user,
                                "json_schema": (
                                    LessonSlidePlan
                                    .model_json_schema()
                                ),
                            },
                        )

                        raw = {}
                        try:
                            plan = (
                                self.backend
                                .generate_structured(
                                    LessonSlidePlan,
                                    system=system,
                                    user=user,
                                )
                            )
                            raw = plan.model_dump(
                                mode="json"
                            )
                            self._write_json(
                                response_path,
                                raw,
                            )

                            if (
                                plan.lesson_id
                                != lesson.lesson_id
                            ):
                                raise ValueError(
                                    "slide plan returned "
                                    "wrong lesson_id"
                                )
                            self._validate_plan_artifacts(
                                plan=plan,
                                lesson_manifest=(
                                    lesson_manifest
                                ),
                            )

                            attempts.append(
                                SlideGenerationAttempt(
                                    agent=self.name,
                                    lesson_id=(
                                        lesson.lesson_id
                                    ),
                                    attempt=attempt,
                                    succeeded=True,
                                    request_path=str(
                                        request_path
                                    ),
                                    response_path=str(
                                        response_path
                                    ),
                                )
                            )
                            plans.append(plan)
                            break

                        except Exception as exc:
                            final_errors = (
                                self._errors(exc)
                            )
                            if (
                                isinstance(
                                    exc,
                                    StructuredOutputError,
                                )
                                and exc.raw_content
                            ):
                                try:
                                    raw = json.loads(
                                        exc.raw_content
                                    )
                                except Exception:
                                    raw = {
                                        "_raw_content": (
                                            exc.raw_content
                                        )
                                    }
                                self._write_json(
                                    response_path,
                                    raw,
                                )

                            attempts.append(
                                SlideGenerationAttempt(
                                    agent=self.name,
                                    lesson_id=(
                                        lesson.lesson_id
                                    ),
                                    attempt=attempt,
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
                                attempt
                                < self.max_attempts
                            ):
                                preview = (
                                    json.dumps(
                                        raw,
                                        ensure_ascii=False,
                                        default=str,
                                    )
                                )
                                if len(preview) > 2500:
                                    preview = (
                                        preview[:2500]
                                        + "...[truncated]"
                                    )

                                user = (
                                    original_user
                                    + "\n\nThe previous slide "
                                    "plan was invalid. Return a "
                                    "fresh complete corrected "
                                    "LessonSlidePlan.\nERRORS:\n- "
                                    + "\n- ".join(
                                        final_errors
                                    )
                                    + "\nDo not invent artifact "
                                    "paths. Previous response "
                                    "preview:\n"
                                    + preview
                                )
                    else:
                        raise ValueError(
                            f"slide planning failed for "
                            f"{lesson.lesson_id}: "
                            + "; ".join(final_errors)
                        )

            course_plan = CourseSlidePlan(
                course_title=outline.title,
                lessons=tuple(plans),
            )

        except Exception as exc:
            failure_outputs = {
                "slide_planning_attempts": [
                    item.model_dump(mode="json")
                    for item in (
                        attempts
                        if "attempts" in locals()
                        else []
                    )
                ]
            }
            self._write_json(
                self.trace_dir / "slide_planning_failure.json",
                {
                    "agent": self.name,
                    "error": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                    **failure_outputs,
                },
            )
            return AgentResult.failed(
                agent_name=self.name,
                errors=(
                    f"{type(exc).__name__}: {exc}",
                ),
                outputs=failure_outputs,
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "slide_plan": (
                    course_plan.model_dump(
                        mode="json"
                    )
                ),
                "slide_planning_attempts": [
                    item.model_dump(
                        mode="json"
                    )
                    for item in attempts
                ],
            },
            metrics={
                "planned_slide_count": sum(
                    len(lesson.slides)
                    for lesson in course_plan.lessons
                ),
                "slide_planner_attempts": (
                    total_attempts
                ),
                "slide_planner_retries": (
                    total_attempts
                    - len(course_plan.lessons)
                ),
            },
        )
