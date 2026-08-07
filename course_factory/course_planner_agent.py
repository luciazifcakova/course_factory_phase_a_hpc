from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseModule, CourseOutline
from .course_specification import CourseSpecification
from .job_context import JobContext
from .lesson_scheduler import LessonScheduler
from .llm_backend import LLMBackend, ensure_structured_backend


class PlannerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    modules: tuple[CourseModule, ...]


class CoursePlannerAgent(Agent):
    name = "course_planner"
    version = "1.1.0"
    capabilities = frozenset({"course_planning"})

    def __init__(
        self,
        backend: LLMBackend,
        scheduler: LessonScheduler | None = None,
    ) -> None:
        self.backend = ensure_structured_backend(backend)
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
            planned = self.backend.generate_structured(
                PlannerResponse,
                system=(
                    "You are an expert R instructor. Build a concise, "
                    "pedagogically ordered course plan. Use only supplied "
                    "course specification and knowledge. Do not exceed the "
                    "requested duration. Preserve knowledge IDs."
                ),
                user=(
                    f"COURSE SPECIFICATION:\n{spec.model_dump_json(indent=2)}\n\n"
                    f"LOCAL KNOWLEDGE:\n{local_knowledge}"
                ),
            )
            schedule = self.scheduler.schedule(
                modules=planned.modules,
                total_duration_minutes=spec.duration_minutes,
            )
            outline = CourseOutline(
                title=spec.title,
                audience=spec.audience,
                language=spec.language,
                modules=schedule.modules,
                learning_objectives=spec.learning_objectives,
                required_packages=tuple(sorted(
                    set(spec.required_packages).union(
                        package
                        for module in schedule.modules
                        for lesson in module.lessons
                        for package in lesson.required_packages
                    )
                )),
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
                    "lesson_count": sum(len(m.lessons) for m in schedule.modules),
                },
            },
            metrics={
                "module_count": len(schedule.modules),
                "lesson_count": sum(len(m.lessons) for m in schedule.modules),
                "scheduled_minutes": schedule.scheduled_minutes,
            },
        )
