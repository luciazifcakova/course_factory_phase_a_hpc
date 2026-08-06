from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

class CourseSpecification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=3)
    topic: str = Field(min_length=1)
    audience: str = Field(min_length=2)
    duration_minutes: int = Field(default=180, ge=15, le=2880)
    language: str = Field(default="English", min_length=2)
    delivery_mode: str = Field(default="online")
    level: str = Field(default="beginner")
    prerequisites: tuple[str, ...] = ()
    learning_objectives: tuple[str, ...] = ()
    required_packages: tuple[str, ...] = ()
    exercise_count: int = Field(default=4, ge=0, le=20)
    assumptions: tuple[str, ...] = ()
    clarification_required: bool = False
    clarification_question: str | None = None

    @model_validator(mode="after")
    def validate_clarification(self):
        if self.clarification_required and not self.clarification_question:
            raise ValueError(
                "clarification_question is required when clarification_required is true"
            )
        return self
