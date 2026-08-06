from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

class Lesson(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lesson_id: str = Field(min_length=1)
    title: str = Field(min_length=2)
    duration_minutes: int = Field(ge=5, le=240)
    objectives: tuple[str, ...] = ()
    practical: bool = False
    requires_live_demo: bool = False
    required_packages: tuple[str, ...] = ()
    prerequisites: tuple[str, ...] = ()
    knowledge_ids: tuple[str, ...] = ()

class CourseModule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: str = Field(min_length=1)
    title: str = Field(min_length=2)
    description: str = ""
    lessons: tuple[Lesson, ...] = ()
    prerequisites: tuple[str, ...] = ()

    @property
    def estimated_minutes(self) -> int:
        return sum(lesson.duration_minutes for lesson in self.lessons)

class CourseOutline(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=3)
    audience: str = Field(min_length=2)
    language: str = "English"
    modules: tuple[CourseModule, ...]
    learning_objectives: tuple[str, ...]
    required_packages: tuple[str, ...] = ()
    total_duration_minutes: int = Field(ge=15, le=2880)
    assumptions: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    version: str = "1.0"

    @model_validator(mode="after")
    def validate_duration(self):
        scheduled = sum(module.estimated_minutes for module in self.modules)
        if scheduled > self.total_duration_minutes:
            raise ValueError(
                f"scheduled lesson time ({scheduled}) exceeds course duration "
                f"({self.total_duration_minutes})"
            )
        return self
