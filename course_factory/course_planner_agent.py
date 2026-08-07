from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseModule, CourseOutline, Lesson
from .course_specification import CourseSpecification
from .job_context import JobContext
from .lesson_scheduler import LessonScheduler
from .llm_backend import (
    LLMBackend,
    StructuredOutputError,
    ensure_structured_backend,
)


DependencyId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=32,
        pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$",
    ),
]


class PlannerLesson(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    lesson_id: DependencyId
    title: str = Field(min_length=2, max_length=120)
    duration_minutes: int = Field(ge=5, le=180)
    objectives: tuple[str, ...] = Field(default=(), max_length=6)
    practical: bool = False
    requires_live_demo: bool = False
    required_packages: tuple[str, ...] = Field(default=(), max_length=8)
    prerequisite_lesson_ids: tuple[
        DependencyId,
        ...,
    ] = Field(
        default=(),
        max_length=4,
        validation_alias=AliasChoices(
            "prerequisite_lesson_ids",
            "prerequisites",
        ),
        serialization_alias="prerequisite_lesson_ids",
        description=(
            "IDs of EARLIER lessons in this same returned course plan."
        ),
    )
    knowledge_ids: tuple[str, ...] = Field(default=(), max_length=20)


class PlannerModule(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    module_id: DependencyId
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    lessons: tuple[PlannerLesson, ...] = Field(
        min_length=1,
        max_length=8,
    )
    prerequisite_module_ids: tuple[
        DependencyId,
        ...,
    ] = Field(
        default=(),
        max_length=4,
        validation_alias=AliasChoices(
            "prerequisite_module_ids",
            "prerequisites",
        ),
        serialization_alias="prerequisite_module_ids",
        description=(
            "IDs of EARLIER modules in this same returned course plan."
        ),
    )


class PlannerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    modules: tuple[PlannerModule, ...] = Field(
        min_length=1,
        max_length=8,
    )

    @model_validator(mode="after")
    def validate_dependency_references(
        self,
    ) -> "PlannerResponse":
        module_ids = [m.module_id for m in self.modules]
        if len(module_ids) != len(set(module_ids)):
            raise ValueError("module_id values must be unique")

        module_set = set(module_ids)
        module_index = {
            module_id: index
            for index, module_id in enumerate(module_ids)
        }

        for module in self.modules:
            if module.module_id in module.prerequisite_module_ids:
                raise ValueError(
                    f"module {module.module_id!r} cannot depend on itself"
                )
            unknown = (
                set(module.prerequisite_module_ids) - module_set
            )
            if unknown:
                raise ValueError(
                    f"module {module.module_id!r} references unknown "
                    "prerequisite module IDs: "
                    + ", ".join(sorted(unknown))
                )
            forward = [
                dep
                for dep in module.prerequisite_module_ids
                if module_index[dep] >= module_index[module.module_id]
            ]
            if forward:
                raise ValueError(
                    f"module {module.module_id!r} may depend only on "
                    "earlier modules; invalid: "
                    + ", ".join(sorted(forward))
                )

        lessons = [
            lesson
            for module in self.modules
            for lesson in module.lessons
        ]
        if not lessons:
            raise ValueError(
                "course plan must contain at least one lesson"
            )
        if len(lessons) > 24:
            raise ValueError(
                "course plan contains too many lessons"
            )

        lesson_ids = [lesson.lesson_id for lesson in lessons]
        if len(lesson_ids) != len(set(lesson_ids)):
            raise ValueError(
                "lesson_id values must be globally unique"
            )

        lesson_set = set(lesson_ids)
        lesson_index = {
            lesson_id: index
            for index, lesson_id in enumerate(lesson_ids)
        }

        for lesson in lessons:
            if lesson.lesson_id in lesson.prerequisite_lesson_ids:
                raise ValueError(
                    f"lesson {lesson.lesson_id!r} cannot depend on itself"
                )
            unknown = (
                set(lesson.prerequisite_lesson_ids) - lesson_set
            )
            if unknown:
                raise ValueError(
                    f"lesson {lesson.lesson_id!r} references unknown "
                    "prerequisite lesson IDs: "
                    + ", ".join(sorted(unknown))
                )
            forward = [
                dep
                for dep in lesson.prerequisite_lesson_ids
                if lesson_index[dep] >= lesson_index[lesson.lesson_id]
            ]
            if forward:
                raise ValueError(
                    f"lesson {lesson.lesson_id!r} may depend only on "
                    "earlier lessons; invalid: "
                    + ", ".join(sorted(forward))
                )

        return self


class CoursePlannerAgent(Agent):
    name = "course_planner"
    version = "1.3.0"
    capabilities = frozenset({"course_planning"})

    def __init__(
        self,
        backend: LLMBackend,
        scheduler: LessonScheduler | None = None,
        *,
        trace_dir: str | Path | None = None,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        self.backend = ensure_structured_backend(backend)
        self.scheduler = scheduler or LessonScheduler()
        self.trace_dir = Path(trace_dir) if trace_dir else None
        self.max_attempts = max_attempts

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
    def _system_prompt() -> str:
        return (
            "You are an expert R instructor. Build a compact, "
            "pedagogically ordered course plan that conforms exactly "
            "to the supplied JSON schema. Every module MUST contain at "
            "least one lesson. For a course around 180 minutes, normally "
            "create 1-4 modules and 3-6 lessons total. Do not create "
            "dozens of modules or hundreds/thousands of IDs. "
            "Course/background prerequisites belong only to the course "
            "specification and MUST NOT appear in graph dependency IDs. "
            "prerequisite_module_ids may contain only EARLIER module IDs "
            "from this returned plan. prerequisite_lesson_ids may contain "
            "only EARLIER lesson IDs. Use at most four dependency IDs per "
            "item. The sum of lesson durations should closely match the "
            "requested duration. Use short IDs such as mod_001 and LES-001."
        )

    @staticmethod
    def _base_user_prompt(
        *,
        spec: CourseSpecification,
        local_knowledge,
    ) -> str:
        return (
            "COURSE SPECIFICATION:\n"
            f"{spec.model_dump_json(indent=2)}\n\n"
            "BACKGROUND PREREQUISITES (NOT graph IDs):\n"
            f"{list(spec.prerequisites)!r}\n\n"
            "LOCAL KNOWLEDGE:\n"
            f"{local_knowledge}\n\n"
            f"REQUESTED DURATION: {spec.duration_minutes} minutes"
        )

    @staticmethod
    def _repair_prompt(
        *,
        original_user: str,
        error: str,
        previous_response,
    ) -> str:
        preview = json.dumps(
            previous_response,
            ensure_ascii=False,
            default=str,
        )
        if len(preview) > 2000:
            preview = preview[:2000] + "...[previous response truncated]"

        return (
            original_user
            + "\n\nThe previous plan was invalid. Generate a FRESH "
            "COMPLETE plan from scratch. Do not continue the previous "
            "output.\n\nERROR:\n"
            + error
            + "\n\nHARD RULES:\n"
            "- 1-8 modules total; for ~180 minutes normally 1-4.\n"
            "- every module contains 1-8 lessons.\n"
            "- for ~180 minutes normally 3-6 lessons total.\n"
            "- dependencies reference only EARLIER IDs.\n"
            "- maximum four dependency IDs per item.\n"
            "- never generate hundreds or thousands of IDs.\n"
            "- lesson durations must meaningfully fill the requested time.\n"
            "\nPREVIOUS RESPONSE PREVIEW ONLY:\n"
            + preview
        )

    @staticmethod
    def _to_course_modules(
        planned: PlannerResponse,
    ) -> tuple[CourseModule, ...]:
        return tuple(
            CourseModule(
                module_id=module.module_id,
                title=module.title,
                description=module.description,
                prerequisites=module.prerequisite_module_ids,
                lessons=tuple(
                    Lesson(
                        lesson_id=lesson.lesson_id,
                        title=lesson.title,
                        duration_minutes=lesson.duration_minutes,
                        objectives=lesson.objectives,
                        practical=lesson.practical,
                        requires_live_demo=lesson.requires_live_demo,
                        required_packages=lesson.required_packages,
                        prerequisites=lesson.prerequisite_lesson_ids,
                        knowledge_ids=lesson.knowledge_ids,
                    )
                    for lesson in module.lessons
                ),
            )
            for module in planned.modules
        )

    @staticmethod
    def _validate_plan_coverage(
        *,
        planned: PlannerResponse,
        requested_minutes: int,
    ) -> None:
        total = sum(
            lesson.duration_minutes
            for module in planned.modules
            for lesson in module.lessons
        )

        # 50% is a compatibility-safe hard floor. The prompt asks the
        # model to fill the requested duration much more closely.
        minimum = max(5, int(requested_minutes * 0.50))
        maximum = int(requested_minutes * 1.10)

        if total < minimum:
            raise ValueError(
                f"planned duration is too short: {total} minutes for a "
                f"{requested_minutes}-minute course; minimum accepted "
                f"is {minimum}"
            )
        if total > maximum:
            raise ValueError(
                f"planned duration is too long: {total} minutes for a "
                f"{requested_minutes}-minute course; maximum accepted "
                f"is {maximum}"
            )

    def _generate_valid_plan(
        self,
        *,
        spec: CourseSpecification,
        local_knowledge,
    ):
        system = self._system_prompt()
        original_user = self._base_user_prompt(
            spec=spec,
            local_knowledge=local_knowledge,
        )
        user = original_user
        previous_response = {}
        last_error = ""

        for attempt in range(1, self.max_attempts + 1):
            response_path = None
            if self.trace_dir is not None:
                request_path = (
                    self.trace_dir
                    / f"attempt_{attempt:02d}_request.json"
                )
                response_path = (
                    self.trace_dir
                    / f"attempt_{attempt:02d}_response.json"
                )
                self._write_json(
                    request_path,
                    {
                        "attempt": attempt,
                        "system": system,
                        "user": user,
                        "json_schema": PlannerResponse.model_json_schema(),
                    },
                )

            try:
                planned = self.backend.generate_structured(
                    PlannerResponse,
                    system=system,
                    user=user,
                )
                previous_response = planned.model_dump(
                    mode="json",
                    by_alias=True,
                )

                if response_path is not None:
                    self._write_json(
                        response_path,
                        previous_response,
                    )

                self._validate_plan_coverage(
                    planned=planned,
                    requested_minutes=spec.duration_minutes,
                )

                modules = self._to_course_modules(planned)
                schedule = self.scheduler.schedule(
                    modules=modules,
                    total_duration_minutes=spec.duration_minutes,
                )
                if schedule.scheduled_minutes <= 0:
                    raise ValueError(
                        "scheduler produced zero scheduled minutes"
                    )

                if self.trace_dir is not None:
                    self._write_json(
                        self.trace_dir / "result.json",
                        {
                            "succeeded": True,
                            "attempts": attempt,
                            "scheduled_minutes": schedule.scheduled_minutes,
                        },
                    )
                return planned, schedule, attempt

            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"

                if (
                    isinstance(exc, StructuredOutputError)
                    and exc.raw_content
                ):
                    try:
                        previous_response = json.loads(exc.raw_content)
                    except Exception:
                        previous_response = {
                            "_raw_content": exc.raw_content
                        }
                    if response_path is not None:
                        self._write_json(
                            response_path,
                            previous_response,
                        )

                if self.trace_dir is not None:
                    self._write_json(
                        self.trace_dir
                        / f"attempt_{attempt:02d}_validation.json",
                        {
                            "attempt": attempt,
                            "error": last_error,
                        },
                    )

                if attempt < self.max_attempts:
                    user = self._repair_prompt(
                        original_user=original_user,
                        error=last_error,
                        previous_response=previous_response,
                    )

        if self.trace_dir is not None:
            self._write_json(
                self.trace_dir / "result.json",
                {
                    "succeeded": False,
                    "attempts": self.max_attempts,
                    "error": last_error,
                },
            )

        raise ValueError(
            f"course plan failed after {self.max_attempts} attempts: "
            f"{last_error}"
        )

    def run(
        self,
        context: JobContext,
    ) -> AgentResult:
        spec_raw = context.state.get("course_specification")
        if not isinstance(spec_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_specification is missing",),
            )

        try:
            spec = CourseSpecification.model_validate(spec_raw)
            local_knowledge = context.state.get(
                "local_knowledge_results",
                [],
            )
            _, schedule, attempts = self._generate_valid_plan(
                spec=spec,
                local_knowledge=local_knowledge,
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
                    if isinstance(item, dict)
                    and item.get("document_id")
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
                        len(module.lessons)
                        for module in schedule.modules
                    ),
                },
            },
            metrics={
                "module_count": len(schedule.modules),
                "lesson_count": sum(
                    len(module.lessons)
                    for module in schedule.modules
                ),
                "scheduled_minutes": schedule.scheduled_minutes,
                "planner_attempts": attempts,
                "planner_retries": max(0, attempts - 1),
            },
        )
