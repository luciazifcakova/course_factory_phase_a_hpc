from __future__ import annotations

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline, Lesson
from .course_specification import CourseSpecification
from .job_context import JobContext
from .lesson_content_models import LessonContent, LessonContentSet
from .llm_backend import LLMBackend


LESSON_SCHEMA = '''{
  "lesson_id": "lesson identifier supplied in the request",
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
    version = "1.0.0"
    capabilities = frozenset({"lesson_generation"})

    def __init__(self, backend: LLMBackend) -> None:
        self.backend = backend

    def _generate_lesson(
        self,
        *,
        specification: CourseSpecification,
        outline: CourseOutline,
        lesson: Lesson,
    ) -> LessonContent:
        raw = self.backend.generate_json(
            system=(
                "You are an expert R instructor writing accurate, "
                "beginner-friendly lesson material. Follow the supplied "
                "lesson plan exactly. Do not invent package functions or "
                "claim that code was executed. Use plain teaching prose. "
                "Preserve the supplied lesson_id and only use source IDs "
                "that appear in the lesson knowledge_ids."
            ),
            user=(
                "COURSE SPECIFICATION:\n"
                f"{specification.model_dump_json(indent=2)}\n\n"
                "COURSE OUTLINE SUMMARY:\n"
                f"title={outline.title!r}\n"
                f"audience={outline.audience!r}\n"
                f"language={outline.language!r}\n\n"
                "LESSON TO WRITE:\n"
                f"{lesson.model_dump_json(indent=2)}"
            ),
            schema_hint=LESSON_SCHEMA,
        )
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
                f"Practical lesson {lesson.lesson_id!r} requires an activity."
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

    def run(self, context: JobContext) -> AgentResult:
        specification_raw = context.state.get("course_specification")
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

            lessons = tuple(
                self._generate_lesson(
                    specification=specification,
                    outline=outline,
                    lesson=lesson,
                )
                for module in outline.modules
                for lesson in module.lessons
            )

            planned_ids = tuple(
                lesson.lesson_id
                for module in outline.modules
                for lesson in module.lessons
            )
            generated_ids = tuple(
                lesson.lesson_id for lesson in lessons
            )
            if generated_ids != planned_ids:
                raise ValueError(
                    "Generated lesson order does not match the course outline."
                )

            content_set = LessonContentSet(
                course_title=outline.title,
                lessons=lessons,
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
            },
        )
