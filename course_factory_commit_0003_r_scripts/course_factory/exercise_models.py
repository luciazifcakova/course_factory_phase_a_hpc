from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, model_validator

class ExerciseType(StrEnum):
    CODE = "code"
    INTERPRETATION = "interpretation"
    DEBUGGING = "debugging"
    SHORT_ANSWER = "short_answer"

class Exercise(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exercise_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    title: str = Field(min_length=3)
    exercise_type: ExerciseType
    instructions: str = Field(min_length=10)
    estimated_minutes: int = Field(ge=5, le=180)
    difficulty: str = Field(default="beginner")
    starter_code: str | None = None
    hints: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    required_packages: tuple[str, ...] = ()
    knowledge_ids: tuple[str, ...] = ()

class ExerciseSolution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exercise_id: str
    solution_text: str = Field(min_length=5)
    solution_code: str | None = None
    explanation: str = Field(min_length=5)
    grading_points: tuple[str, ...] = ()

class ExerciseSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    course_title: str = Field(min_length=3)
    exercises: tuple[Exercise, ...]
    solutions: tuple[ExerciseSolution, ...] = ()

    @model_validator(mode="after")
    def validate_links(self):
        exercise_ids = [item.exercise_id for item in self.exercises]
        if len(exercise_ids) != len(set(exercise_ids)):
            raise ValueError("exercise_id values must be unique")

        solution_ids = [item.exercise_id for item in self.solutions]
        unknown = set(solution_ids) - set(exercise_ids)
        if unknown:
            raise ValueError(f"solutions reference unknown exercises: {sorted(unknown)}")
        return self
