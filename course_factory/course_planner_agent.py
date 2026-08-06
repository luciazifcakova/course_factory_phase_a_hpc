from __future__ import annotations

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseModule, CourseOutline, Lesson
from .course_specification import CourseSpecification
from .job_context import JobContext
from .lesson_scheduler import LessonScheduler
from .llm_backend import LLMBackend

PLANNER_SCHEMA = '''{
  "modules": [
    {
      "module_id": "string",
      "title": "string",
      "description": "string",
      "prerequisites": ["module_id"],
      "lessons": [
        {
          "lesson_id": "string",
          "title": "string",
          "duration_minutes": 30,
          "objectives": ["string"],
          "practical": true,
          "requires_live_demo": false,
          "required_packages": ["string"],
          "prerequisites": ["lesson_id"],
          "knowledge_ids": ["DOC-..."]
        }
      ]
    }
  ]
}'''

class CoursePlannerAgent(Agent):
    name = "course_planner"
    version = "1.0.0"
    capabilities = frozenset({"course_planning"})

    def __init__(
        self,
        backend: LLMBackend,
        scheduler: LessonScheduler | None = None,
    ) -> None:
        self.backend = backend
        self.scheduler = scheduler or LessonScheduler()

    def run(self, context: JobContext) -> AgentResult:
        spec_raw = context.state.get("course_specification")
        if not isinstance(spec_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_specification is missing",),
            )

        try:
            spec = CourseSpecification.model_validate(spec_raw)
            local_knowledge = context.state.get("local_knowledge_results", [])
            raw = self.backend.generate_json(
                system=(
                    "You are an expert R instructor. Build a concise, pedagogically ordered "
                    "course plan. Use only the supplied course specification and knowledge. "
                    "Do not exceed the requested duration. Preserve knowledge IDs."
                ),
                user=(
                    f"COURSE SPECIFICATION:\n{spec.model_dump_json(indent=2)}\n\n"
                    f"LOCAL KNOWLEDGE:\n{local_knowledge}"
                ),
                schema_hint=PLANNER_SCHEMA,
            )

            modules = tuple(
                CourseModule(
                    module_id=item["module_id"],
                    title=item["title"],
                    description=item.get("description", ""),
                    prerequisites=tuple(item.get("prerequisites", [])),
                    lessons=tuple(
                        Lesson(
                            lesson_id=lesson["lesson_id"],
                            title=lesson["title"],
                            duration_minutes=lesson["duration_minutes"],
                            objectives=tuple(lesson.get("objectives", [])),
                            practical=bool(lesson.get("practical", False)),
                            requires_live_demo=bool(
                                lesson.get("requires_live_demo", False)
                            ),
                            required_packages=tuple(
                                lesson.get("required_packages", [])
                            ),
                            prerequisites=tuple(
                                lesson.get("prerequisites", [])
                            ),
                            knowledge_ids=tuple(
                                lesson.get("knowledge_ids", [])
                            ),
                        )
                        for lesson in item.get("lessons", [])
                    ),
                )
                for item in raw["modules"]
            )

            schedule = self.scheduler.schedule(
                modules=modules,
                total_duration_minutes=spec.duration_minutes,
            )

            outline = CourseOutline(
                title=spec.title,
                audience=spec.audience,
                language=spec.language,
                modules=schedule.modules,
                learning_objectives=spec.learning_objectives,
                required_packages=tuple(
                    sorted(
                        set(spec.required_packages).union(
                            package
                            for module in schedule.modules
                            for lesson in module.lessons
                            for package in lesson.required_packages
                        )
                    )
                ),
                total_duration_minutes=spec.duration_minutes,
                assumptions=spec.assumptions,
                references=tuple(
                    str(item.get("document_id"))
                    for item in local_knowledge
                    if isinstance(item, dict) and item.get("document_id")
                ),
            )

        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "course_outline": outline.model_dump(mode="json"),
                "schedule_summary": {
                    "scheduled_minutes": schedule.scheduled_minutes,
                    "unscheduled_minutes": schedule.unscheduled_minutes,
                    "module_count": len(schedule.modules),
                    "lesson_count": sum(
                        len(module.lessons) for module in schedule.modules
                    ),
                },
            },
            metrics={
                "module_count": len(schedule.modules),
                "lesson_count": sum(
                    len(module.lessons) for module in schedule.modules
                ),
                "scheduled_minutes": schedule.scheduled_minutes,
            },
        )
