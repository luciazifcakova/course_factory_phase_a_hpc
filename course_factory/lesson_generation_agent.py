from __future__ import annotations

import json
from pathlib import Path
import re

from pydantic import ValidationError

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline, Lesson
from .course_specification import CourseSpecification
from .job_context import JobContext
from .lesson_content_models import LessonContent, LessonContentSet
from .llm_backend import LLMBackend, StructuredOutputError, ensure_structured_backend


LESSON_SCHEMA = '''{
  "lesson_id": "exact lesson identifier supplied in the request",
  "title": "lesson title",
  "summary": "concise lesson overview",
  "sections": [
    {
      "heading": "section heading",
      "content": "clear teaching explanation in prose",
      "bullet_points": ["optional supporting point"]
    }
  ],
  "key_takeaways": ["important concept"],
  "practical_activity": {
    "title": "activity title",
    "instructions": ["step one", "step two"],
    "expected_result": "what the learner should produce or observe",
    "estimated_minutes": 15
  },
  "instructor_notes": ["optional teaching note"],
  "source_ids": ["preserve supplied knowledge IDs only"]
}'''


class LessonGenerationAgent(Agent):
    name = "lesson_generation"
    version = "1.1.0"
    capabilities = frozenset({"lesson_generation"})

    def __init__(
        self,
        backend: LLMBackend,
        *,
        trace_dir: str | Path | None = None,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.backend = ensure_structured_backend(backend)
        self.trace_dir = Path(trace_dir) if trace_dir else None
        self.max_attempts = max_attempts

    @staticmethod
    def _safe(value: str) -> str:
        return (
            re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
            .strip("._")
            or "lesson"
        )

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
    def _validation_messages(
        exc: Exception,
    ) -> tuple[str, ...]:
        if isinstance(exc, ValidationError):
            return tuple(
                (
                    ".".join(str(part) for part in item["loc"])
                    + ": "
                    + item["msg"]
                )
                for item in exc.errors()
            )
        return (f"{type(exc).__name__}: {exc}",)

    @staticmethod
    def _base_system_prompt() -> str:
        return (
            "You are an expert R instructor writing accurate, "
            "beginner-friendly lesson material. Follow the supplied "
            "lesson plan exactly. Return JSON only. The top-level JSON "
            "object MUST contain lesson_id, title, summary, sections, "
            "key_takeaways, practical_activity, instructor_notes, and "
            "source_ids. sections MUST be an array of objects; never put "
            "key_takeaways or another top-level field inside sections. "
            "Do not invent package functions or claim that code was "
            "executed. Preserve the supplied lesson_id and only use "
            "source IDs that appear in lesson knowledge_ids."
        )

    @staticmethod
    def _base_user_prompt(
        *,
        specification: CourseSpecification,
        outline: CourseOutline,
        lesson: Lesson,
    ) -> str:
        return (
            "COURSE SPECIFICATION:\n"
            f"{specification.model_dump_json(indent=2)}\n\n"
            "COURSE OUTLINE SUMMARY:\n"
            f"title={outline.title!r}\n"
            f"audience={outline.audience!r}\n"
            f"language={outline.language!r}\n\n"
            "LESSON TO WRITE:\n"
            f"{lesson.model_dump_json(indent=2)}"
        )

    @staticmethod
    def _repair_prompt(
        *,
        original_user: str,
        previous_response: dict,
        errors: tuple[str, ...],
    ) -> str:
        return (
            original_user
            + "\n\nYour previous JSON did not satisfy the lesson schema. "
            "Return the COMPLETE corrected JSON object again. Do not "
            "return a patch or explanation.\n\n"
            "VALIDATION ERRORS:\n- "
            + "\n- ".join(errors)
            + "\n\nIMPORTANT STRUCTURE RULES:\n"
            "- sections must contain only section objects with heading, "
            "content, and bullet_points.\n"
            "- key_takeaways must be a separate top-level array.\n"
            "- practical_activity must be a top-level object or null.\n"
            "- instructor_notes and source_ids must be top-level arrays.\n"
            "- preserve the exact lesson_id.\n\n"
            "PREVIOUS RESPONSE:\n"
            + json.dumps(
                previous_response,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )

    def _validate_content(
        self,
        *,
        raw: dict,
        lesson: Lesson,
    ) -> LessonContent:
        content = LessonContent.model_validate(raw)

        if content.lesson_id != lesson.lesson_id:
            raise ValueError(
                f"LLM returned lesson_id {content.lesson_id!r}; "
                f"expected {lesson.lesson_id!r}."
            )

        allowed_sources = set(lesson.knowledge_ids)
        unknown_sources = set(content.source_ids) - allowed_sources
        if unknown_sources:
            raise ValueError(
                "Lesson contains unknown source IDs: "
                + ", ".join(sorted(unknown_sources))
            )

        if lesson.practical and content.practical_activity is None:
            raise ValueError(
                f"Practical lesson {lesson.lesson_id!r} "
                "requires an activity."
            )

        return content.model_copy(
            update={
                "title": lesson.title,
                "source_ids": tuple(
                    source_id
                    for source_id in content.source_ids
                    if source_id in allowed_sources
                ),
            }
        )

    def _generate_lesson(
        self,
        *,
        specification: CourseSpecification,
        outline: CourseOutline,
        lesson: Lesson,
    ) -> tuple[LessonContent, int]:
        system = self._base_system_prompt()
        original_user = self._base_user_prompt(
            specification=specification,
            outline=outline,
            lesson=lesson,
        )
        user = original_user

        lesson_trace_dir = (
            self.trace_dir / self._safe(lesson.lesson_id)
            if self.trace_dir is not None
            else None
        )

        final_errors: tuple[str, ...] = ()

        for attempt in range(1, self.max_attempts + 1):
            request_path = None
            response_path = None

            if lesson_trace_dir is not None:
                request_path = (
                    lesson_trace_dir
                    / f"attempt_{attempt:02d}_request.json"
                )
                response_path = (
                    lesson_trace_dir
                    / f"attempt_{attempt:02d}_response.json"
                )
                self._write_json(
                    request_path,
                    {
                        "lesson_id": lesson.lesson_id,
                        "attempt": attempt,
                        "system": system,
                        "user": user,
                        "schema_hint": LESSON_SCHEMA,
                    },
                )

            raw: dict = {}
            try:
                content = self.backend.generate_structured(
                    LessonContent,
                    system=system,
                    user=user,
                )
                raw = content.model_dump(mode="json")
                if response_path is not None:
                    self._write_json(response_path, raw)
                content = self._validate_content(
                    raw=raw,
                    lesson=lesson,
                )

                if lesson_trace_dir is not None:
                    self._write_json(
                        lesson_trace_dir / "result.json",
                        {
                            "lesson_id": lesson.lesson_id,
                            "succeeded": True,
                            "attempts": attempt,
                        },
                    )

                return content, attempt

            except Exception as exc:
                if isinstance(exc, StructuredOutputError) and exc.raw_content:
                    try:
                        raw = json.loads(exc.raw_content)
                    except Exception:
                        raw = {"_raw_content": exc.raw_content}
                    if response_path is not None:
                        self._write_json(response_path, raw)
                final_errors = self._validation_messages(exc)

                # Semantic integrity failures should not be repaired by
                # asking the model to invent a different evidence trail.
                # Preserve the original error immediately.
                if (
                    isinstance(exc, ValueError)
                    and "unknown source IDs" in str(exc)
                ):
                    raise

                if lesson_trace_dir is not None:
                    self._write_json(
                        lesson_trace_dir
                        / f"attempt_{attempt:02d}_validation.json",
                        {
                            "lesson_id": lesson.lesson_id,
                            "attempt": attempt,
                            "errors": list(final_errors),
                        },
                    )

                if attempt < self.max_attempts:
                    user = self._repair_prompt(
                        original_user=original_user,
                        previous_response=raw,
                        errors=final_errors,
                    )

        if lesson_trace_dir is not None:
            self._write_json(
                lesson_trace_dir / "result.json",
                {
                    "lesson_id": lesson.lesson_id,
                    "succeeded": False,
                    "attempts": self.max_attempts,
                    "errors": list(final_errors),
                },
            )

        raise ValueError(
            f"Lesson {lesson.lesson_id} failed after "
            f"{self.max_attempts} attempts: "
            + "; ".join(final_errors)
        )

    def run(self, context: JobContext) -> AgentResult:
        specification_raw = context.state.get(
            "course_specification"
        )
        outline_raw = context.state.get("course_outline")

        if not isinstance(specification_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_specification is missing",),
            )
        if not isinstance(outline_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_outline is missing",),
            )

        try:
            specification = CourseSpecification.model_validate(
                specification_raw
            )
            outline = CourseOutline.model_validate(outline_raw)

            lessons: list[LessonContent] = []
            total_attempts = 0
            retried_lessons = 0

            for module in outline.modules:
                for lesson in module.lessons:
                    content, attempts = self._generate_lesson(
                        specification=specification,
                        outline=outline,
                        lesson=lesson,
                    )
                    lessons.append(content)
                    total_attempts += attempts
                    if attempts > 1:
                        retried_lessons += 1

            content_set = LessonContentSet(
                course_title=outline.title,
                lessons=tuple(lessons),
            )
        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "lesson_content": content_set.model_dump(mode="json"),
            },
            metrics={
                "generated_lesson_count": len(content_set.lessons),
                "generated_section_count": sum(
                    len(lesson.sections)
                    for lesson in content_set.lessons
                ),
                "lesson_generation_attempts": total_attempts,
                "retried_lessons": retried_lessons,
            },
        )
