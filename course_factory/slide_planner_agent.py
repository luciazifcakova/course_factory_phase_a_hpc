from __future__ import annotations

import json
from pathlib import Path

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .job_artifacts import ArtifactManifest
from .job_context import JobContext
from .lesson_content_models import LessonContentSet
from .llm_backend import LLMBackend, StructuredOutputError, ensure_structured_backend
from .slide_layout_resolver import SlideLayoutResolver
from .slide_models import CourseSlidePlan, LessonSlideIntent, SlideGenerationAttempt


class SlidePlannerAgent(Agent):
    name = "slide_planner"
    version = "1.1.0"
    capabilities = frozenset({"slide_planning"})

    def __init__(self, backend: LLMBackend, *, trace_dir: str | Path, max_attempts: int = 3) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.backend = ensure_structured_backend(backend)
        self.trace_dir = Path(trace_dir)
        self.max_attempts = max_attempts

    @staticmethod
    def _write_json(path: Path, payload) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    @staticmethod
    def _errors(exc: Exception) -> tuple[str, ...]:
        if isinstance(exc, StructuredOutputError):
            return (str(exc),)
        return (f"{type(exc).__name__}: {exc}",)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are planning EDUCATIONAL INTENT for slides in one R lesson. "
            "Return exactly the supplied JSON schema. Normally create 3-8 slides. "
            "Decide what each slide should teach, not how it is rendered. Never "
            "return layout names. Never return figure paths or script paths. Python "
            "will assign layouts and validated artifacts afterward. Use kind=overview "
            "for the opening, concept for explanation, example for a worked visual "
            "example, code_example when showing code matters, exercise for learner "
            "practice, and summary for takeaways. Set wants_visual=true only when a "
            "visual materially helps. Set wants_code=true only for kind=code_example."
        )

    @staticmethod
    def _user_prompt(*, lesson, lesson_content, lesson_manifest) -> str:
        return (
            "LESSON PLAN:\n" + lesson.model_dump_json(indent=2) + "\n\n"
            "LESSON CONTENT:\n" + lesson_content.model_dump_json(indent=2) + "\n\n"
            "ARTIFACT AVAILABILITY (paths intentionally hidden):\n"
            + json.dumps(
                {
                    "figure_count": len(lesson_manifest.figures),
                    "png_figure_count": sum(i.content_type == "image/png" for i in lesson_manifest.figures),
                    "code_available": lesson_manifest.script is not None,
                },
                indent=2,
            )
            + "\n\nEvery slide lesson_id must be "
            + repr(lesson.lesson_id)
            + ". Use unique slide IDs prefixed with the lesson ID, e.g. "
            + lesson.lesson_id
            + "-S01."
        )

    def run(self, context: JobContext) -> AgentResult:
        outline_raw = context.state.get("course_outline")
        content_raw = context.state.get("lesson_content")
        manifest_raw = context.state.get("artifact_manifest")
        if not isinstance(outline_raw, dict):
            return AgentResult.failed(agent_name=self.name, errors=("course_outline is missing",))
        if not isinstance(content_raw, dict):
            return AgentResult.failed(agent_name=self.name, errors=("lesson_content is missing",))
        if not isinstance(manifest_raw, dict):
            return AgentResult.failed(agent_name=self.name, errors=("artifact_manifest is missing",))

        attempts = []
        try:
            outline = CourseOutline.model_validate(outline_raw)
            content = LessonContentSet.model_validate(content_raw)
            manifest = ArtifactManifest.model_validate(manifest_raw)
            content_by_id = {x.lesson_id: x for x in content.lessons}
            manifest_by_id = {x.lesson_id: x for x in manifest.lessons}
            plans = []
            total_attempts = 0

            for module in outline.modules:
                for lesson in module.lessons:
                    lesson_content = content_by_id[lesson.lesson_id]
                    lesson_manifest = manifest_by_id[lesson.lesson_id]
                    system = self._system_prompt()
                    original_user = self._user_prompt(
                        lesson=lesson,
                        lesson_content=lesson_content,
                        lesson_manifest=lesson_manifest,
                    )
                    user = original_user
                    final_errors = ()

                    for attempt in range(1, self.max_attempts + 1):
                        total_attempts += 1
                        trace = self.trace_dir / lesson.lesson_id
                        request_path = trace / f"attempt_{attempt:02d}_request.json"
                        response_path = trace / f"attempt_{attempt:02d}_response.json"
                        self._write_json(
                            request_path,
                            {"system": system, "user": user, "json_schema": LessonSlideIntent.model_json_schema()},
                        )
                        raw = {}
                        try:
                            intent = self.backend.generate_structured(
                                LessonSlideIntent,
                                system=system,
                                user=user,
                            )
                            raw = intent.model_dump(mode="json")
                            self._write_json(response_path, raw)
                            if intent.lesson_id != lesson.lesson_id:
                                raise ValueError("slide intent returned wrong lesson_id")
                            plans.append(
                                SlideLayoutResolver.resolve(
                                    intent=intent,
                                    lesson_manifest=lesson_manifest,
                                )
                            )
                            attempts.append(
                                SlideGenerationAttempt(
                                    agent=self.name,
                                    lesson_id=lesson.lesson_id,
                                    attempt=attempt,
                                    succeeded=True,
                                    request_path=str(request_path),
                                    response_path=str(response_path),
                                )
                            )
                            break
                        except Exception as exc:
                            final_errors = self._errors(exc)
                            if isinstance(exc, StructuredOutputError) and exc.raw_content:
                                try:
                                    raw = json.loads(exc.raw_content)
                                except Exception:
                                    raw = {"_raw_content": exc.raw_content}
                                self._write_json(response_path, raw)
                            attempts.append(
                                SlideGenerationAttempt(
                                    agent=self.name,
                                    lesson_id=lesson.lesson_id,
                                    attempt=attempt,
                                    succeeded=False,
                                    request_path=str(request_path),
                                    response_path=str(response_path) if response_path.exists() else None,
                                    validation_errors=final_errors,
                                )
                            )
                            if attempt < self.max_attempts:
                                user = (
                                    original_user
                                    + "\n\nThe previous slide-intent response was invalid. Return a fresh "
                                    "complete LessonSlideIntent. Do not return layout names or file paths.\nERRORS:\n- "
                                    + "\n- ".join(final_errors)
                                )
                    else:
                        raise ValueError(
                            f"slide planning failed for {lesson.lesson_id}: " + "; ".join(final_errors)
                        )

            course_plan = CourseSlidePlan(course_title=outline.title, lessons=tuple(plans))
        except Exception as exc:
            failure_outputs = {"slide_planning_attempts": [a.model_dump(mode="json") for a in attempts]}
            self._write_json(
                self.trace_dir / "slide_planning_failure.json",
                {"agent": self.name, "error": f"{type(exc).__name__}: {exc}", **failure_outputs},
            )
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
                outputs=failure_outputs,
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "slide_plan": course_plan.model_dump(mode="json"),
                "slide_planning_attempts": [a.model_dump(mode="json") for a in attempts],
            },
            metrics={
                "planned_slide_count": sum(len(x.slides) for x in course_plan.lessons),
                "slide_planner_attempts": total_attempts,
                "slide_planner_retries": total_attempts - len(course_plan.lessons),
            },
        )
