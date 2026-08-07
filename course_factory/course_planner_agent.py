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
from .course_outline import (
    CourseModule,
    CourseOutline,
    Lesson,
)
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
    title: str = Field(min_length=2)
    duration_minutes: int = Field(ge=5, le=240)
    objectives: tuple[str, ...] = ()
    practical: bool = False
    requires_live_demo: bool = False
    required_packages: tuple[str, ...] = ()

    prerequisite_lesson_ids: tuple[
        DependencyId,
        ...,
    ] = Field(
        default=(),
        validation_alias=AliasChoices(
            "prerequisite_lesson_ids",
            "prerequisites",
        ),
        serialization_alias="prerequisite_lesson_ids",
        description=(
            "IDs of lessons in this same course that must be "
            "completed first. Never put background knowledge here."
        ),
    )

    knowledge_ids: tuple[str, ...] = ()


class PlannerModule(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    module_id: DependencyId
    title: str = Field(min_length=2)
    description: str = ""
    lessons: tuple[PlannerLesson, ...] = ()

    prerequisite_module_ids: tuple[
        DependencyId,
        ...,
    ] = Field(
        default=(),
        validation_alias=AliasChoices(
            "prerequisite_module_ids",
            "prerequisites",
        ),
        serialization_alias="prerequisite_module_ids",
        description=(
            "IDs of modules in this same course that must be "
            "completed first. Never put human-readable background "
            "knowledge here."
        ),
    )


class PlannerResponse(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    modules: tuple[PlannerModule, ...]

    @model_validator(mode="after")
    def validate_dependency_references(
        self,
    ) -> "PlannerResponse":
        module_ids = [
            module.module_id
            for module in self.modules
        ]
        if len(module_ids) != len(set(module_ids)):
            raise ValueError(
                "module_id values must be unique"
            )

        module_id_set = set(module_ids)
        for module in self.modules:
            if (
                module.module_id
                in module.prerequisite_module_ids
            ):
                raise ValueError(
                    f"module {module.module_id!r} cannot depend "
                    "on itself"
                )

            unknown = (
                set(module.prerequisite_module_ids)
                - module_id_set
            )
            if unknown:
                raise ValueError(
                    f"module {module.module_id!r} references "
                    "unknown prerequisite module IDs: "
                    + ", ".join(sorted(unknown))
                )

        lessons = [
            lesson
            for module in self.modules
            for lesson in module.lessons
        ]
        lesson_ids = [
            lesson.lesson_id
            for lesson in lessons
        ]
        if len(lesson_ids) != len(set(lesson_ids)):
            raise ValueError(
                "lesson_id values must be globally unique"
            )

        lesson_id_set = set(lesson_ids)
        for lesson in lessons:
            if (
                lesson.lesson_id
                in lesson.prerequisite_lesson_ids
            ):
                raise ValueError(
                    f"lesson {lesson.lesson_id!r} cannot depend "
                    "on itself"
                )

            unknown = (
                set(lesson.prerequisite_lesson_ids)
                - lesson_id_set
            )
            if unknown:
                raise ValueError(
                    f"lesson {lesson.lesson_id!r} references "
                    "unknown prerequisite lesson IDs: "
                    + ", ".join(sorted(unknown))
                )

        return self


class CoursePlannerAgent(Agent):
    name = "course_planner"
    version = "1.2.0"
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
            raise ValueError(
                "max_attempts must be at least one"
            )
        self.backend = ensure_structured_backend(
            backend
        )
        self.scheduler = scheduler or LessonScheduler()
        self.trace_dir = (
            Path(trace_dir)
            if trace_dir is not None
            else None
        )
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
    def _system_prompt() -> str:
        return (
            "You are an expert R instructor. Build a concise, "
            "pedagogically ordered course plan. Return data that "
            "conforms exactly to the supplied JSON schema. "
            "IMPORTANT: course/background prerequisites such as "
            "'basic R programming knowledge' belong only to the "
            "course specification and MUST NOT appear in module or "
            "lesson dependency fields. "
            "prerequisite_module_ids may contain ONLY module_id "
            "values that occur in this returned plan. "
            "prerequisite_lesson_ids may contain ONLY lesson_id "
            "values that occur in this returned plan. "
            "If the first module has no in-course dependency, use "
            "an empty prerequisite_module_ids array. "
            "Use short machine-readable IDs without spaces, for "
            "example mod_001 and LES-001. Preserve supplied "
            "knowledge IDs. Do not exceed the requested duration."
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
            "BACKGROUND PREREQUISITES (these are NOT module "
            "dependency IDs):\n"
            f"{list(spec.prerequisites)!r}\n\n"
            "LOCAL KNOWLEDGE:\n"
            f"{local_knowledge}"
        )

    @staticmethod
    def _repair_prompt(
        *,
        original_user: str,
        error: str,
        previous_response,
    ) -> str:
        return (
            original_user
            + "\n\nThe previous course plan was invalid. Return "
            "the COMPLETE corrected course-plan JSON again.\n\n"
            "ERROR:\n"
            + error
            + "\n\nDEPENDENCY RULES:\n"
            "- prerequisite_module_ids contains module IDs only.\n"
            "- prerequisite_lesson_ids contains lesson IDs only.\n"
            "- never put prose such as 'basic R knowledge' into "
            "dependency-ID arrays.\n"
            "- every referenced ID must exist in this same plan.\n"
            "- no module or lesson may depend on itself.\n\n"
            "PREVIOUS RESPONSE:\n"
            + json.dumps(
                previous_response,
                indent=2,
                ensure_ascii=False,
                default=str,
            )
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
                prerequisites=(
                    module.prerequisite_module_ids
                ),
                lessons=tuple(
                    Lesson(
                        lesson_id=lesson.lesson_id,
                        title=lesson.title,
                        duration_minutes=(
                            lesson.duration_minutes
                        ),
                        objectives=lesson.objectives,
                        practical=lesson.practical,
                        requires_live_demo=(
                            lesson.requires_live_demo
                        ),
                        required_packages=(
                            lesson.required_packages
                        ),
                        prerequisites=(
                            lesson.prerequisite_lesson_ids
                        ),
                        knowledge_ids=lesson.knowledge_ids,
                    )
                    for lesson in module.lessons
                ),
            )
            for module in planned.modules
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
        last_error = ""
        previous_response = {}

        for attempt in range(
            1,
            self.max_attempts + 1,
        ):
            request_path = None
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
                        "json_schema": (
                            PlannerResponse
                            .model_json_schema()
                        ),
                    },
                )

            try:
                planned = (
                    self.backend.generate_structured(
                        PlannerResponse,
                        system=system,
                        user=user,
                    )
                )
                previous_response = (
                    planned.model_dump(
                        mode="json",
                        by_alias=True,
                    )
                )

                if response_path is not None:
                    self._write_json(
                        response_path,
                        previous_response,
                    )

                modules = self._to_course_modules(
                    planned
                )

                # Semantic graph validation happens here.
                # This catches cycles as well as invalid
                # dependency graphs that cannot be represented
                # by the static JSON schema alone.
                schedule = self.scheduler.schedule(
                    modules=modules,
                    total_duration_minutes=(
                        spec.duration_minutes
                    ),
                )

                if self.trace_dir is not None:
                    self._write_json(
                        self.trace_dir / "result.json",
                        {
                            "succeeded": True,
                            "attempts": attempt,
                        },
                    )

                return planned, schedule, attempt

            except Exception as exc:
                last_error = (
                    f"{type(exc).__name__}: {exc}"
                )

                if (
                    isinstance(
                        exc,
                        StructuredOutputError,
                    )
                    and exc.raw_content
                ):
                    try:
                        previous_response = json.loads(
                            exc.raw_content
                        )
                    except Exception:
                        previous_response = {
                            "_raw_content": (
                                exc.raw_content
                            )
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
                        previous_response=(
                            previous_response
                        ),
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
            "course plan failed after "
            f"{self.max_attempts} attempts: "
            f"{last_error}"
        )

    def run(
        self,
        context: JobContext,
    ) -> AgentResult:
        spec_raw = context.state.get(
            "course_specification"
        )
        if not isinstance(spec_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=(
                    "course_specification is missing",
                ),
            )

        try:
            spec = CourseSpecification.model_validate(
                spec_raw
            )
            local_knowledge = context.state.get(
                "local_knowledge_results",
                [],
            )

            (
                planned,
                schedule,
                attempts,
            ) = self._generate_valid_plan(
                spec=spec,
                local_knowledge=local_knowledge,
            )

            outline = CourseOutline(
                title=spec.title,
                audience=spec.audience,
                language=spec.language,
                modules=schedule.modules,
                learning_objectives=(
                    spec.learning_objectives
                ),
                required_packages=tuple(
                    sorted(
                        set(
                            spec.required_packages
                        ).union(
                            package
                            for module
                            in schedule.modules
                            for lesson
                            in module.lessons
                            for package
                            in lesson.required_packages
                        )
                    )
                ),
                total_duration_minutes=(
                    spec.duration_minutes
                ),
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
                errors=(
                    f"{type(exc).__name__}: {exc}",
                ),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "course_outline": (
                    outline.model_dump(
                        mode="json"
                    )
                ),
                "schedule_summary": {
                    "scheduled_minutes": (
                        schedule.scheduled_minutes
                    ),
                    "unscheduled_minutes": (
                        schedule.unscheduled_minutes
                    ),
                    "module_count": len(
                        schedule.modules
                    ),
                    "lesson_count": sum(
                        len(module.lessons)
                        for module
                        in schedule.modules
                    ),
                },
            },
            metrics={
                "module_count": len(
                    schedule.modules
                ),
                "lesson_count": sum(
                    len(module.lessons)
                    for module in schedule.modules
                ),
                "scheduled_minutes": (
                    schedule.scheduled_minutes
                ),
                "planner_attempts": attempts,
                "planner_retries": max(
                    0,
                    attempts - 1,
                ),
            },
        )
