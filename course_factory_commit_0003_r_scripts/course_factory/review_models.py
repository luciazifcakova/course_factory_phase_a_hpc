from __future__ import annotations
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

class ReviewSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"

class ReviewIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    code: str
    severity: ReviewSeverity
    message: str
    field: str | None = None

class ReviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    artifact_name: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    issues: tuple[ReviewIssue, ...] = ()
    recommendations: tuple[str, ...] = ()

class RepairResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    artifact_name: str
    repaired_payload: dict
    change_summary: tuple[str, ...] = ()
    attempt: int = Field(ge=1, le=3)
