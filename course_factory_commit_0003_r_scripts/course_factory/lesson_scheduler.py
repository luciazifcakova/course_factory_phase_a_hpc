from __future__ import annotations

from dataclasses import dataclass

from .course_outline import CourseModule
from .module_graph import ModuleGraph

@dataclass(frozen=True, slots=True)
class ScheduleResult:
    modules: tuple[CourseModule, ...]
    scheduled_minutes: int
    unscheduled_minutes: int

class LessonScheduler:
    def schedule(
        self,
        *,
        modules: tuple[CourseModule, ...],
        total_duration_minutes: int,
    ) -> ScheduleResult:
        if total_duration_minutes < 15:
            raise ValueError("total_duration_minutes must be at least 15")

        by_id = {module.module_id: module for module in modules}
        if len(by_id) != len(modules):
            raise ValueError("module_id values must be unique")

        graph = ModuleGraph()
        for module in modules:
            graph.add_module(module.module_id)
        for module in modules:
            for prerequisite in module.prerequisites:
                if prerequisite not in by_id:
                    raise ValueError(
                        f"module {module.module_id!r} references unknown prerequisite "
                        f"{prerequisite!r}"
                    )
                graph.depends_on(module.module_id, prerequisite)

        ordered = tuple(by_id[module_id] for module_id in graph.ordered_modules())
        scheduled_minutes = sum(module.estimated_minutes for module in ordered)
        if scheduled_minutes > total_duration_minutes:
            raise ValueError(
                f"course requires {scheduled_minutes} minutes but only "
                f"{total_duration_minutes} are available"
            )

        return ScheduleResult(
            modules=ordered,
            scheduled_minutes=scheduled_minutes,
            unscheduled_minutes=total_duration_minutes - scheduled_minutes,
        )
