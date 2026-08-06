from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CourseArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    path: str
    content_type: str = "application/json"


class CreateCourseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    status: str
    current_step: str
    job_directory: str
    artifacts: tuple[CourseArtifact, ...] = ()
    message: str
    errors: tuple[str, ...] = ()
    metrics: dict[str, int | float | str | bool] = Field(
        default_factory=dict
    )
