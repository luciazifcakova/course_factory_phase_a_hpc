from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, model_validator

class TaskType(StrEnum):
    R_SCRIPT = "r_script"
    FIGURE = "figure"
    TABLE = "table"
    EXERCISE = "exercise"
    SLIDE_CONTENT = "slide_content"

class WorkflowTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    task_type: TaskType
    lesson_id: str = Field(min_length=1)
    description: str = Field(min_length=2)
    input_artifacts: tuple[str, ...] = ()
    output_artifacts: tuple[str, ...] = ()
    depends_on: tuple[str, ...] = ()
    required_packages: tuple[str, ...] = ()
    estimated_minutes: int = Field(default=1, ge=1, le=240)
    max_retries: int = Field(default=2, ge=0, le=3)

class WorkflowPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    course_title: str = Field(min_length=3)
    tasks: tuple[WorkflowTask, ...]
    version: str = "1.0"

    @model_validator(mode="after")
    def validate_dependencies(self):
        task_ids = {task.task_id for task in self.tasks}
        if len(task_ids) != len(self.tasks):
            raise ValueError("task_id values must be unique")
        for task in self.tasks:
            unknown = set(task.depends_on) - task_ids
            if unknown:
                raise ValueError(
                    f"task {task.task_id!r} has unknown dependencies: {sorted(unknown)}"
                )
            if task.task_id in task.depends_on:
                raise ValueError(f"task {task.task_id!r} cannot depend on itself")
        return self
