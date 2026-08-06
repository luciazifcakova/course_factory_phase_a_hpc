from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

class Action(StrEnum):
    BUILD_INPUT = "build_input"
    LOCAL_RETRIEVAL = "local_retrieval"
    FUSE_EVIDENCE = "fuse_evidence"
    ASSESS_KNOWLEDGE = "assess_knowledge"
    ITERATIVE_RETRIEVAL = "iterative_retrieval"
    COURSE_PLANNING = "course_planning"
    WORKFLOW_PLANNING = "workflow_planning"
    R_CODE_GENERATION = "r_code_generation"
    SECURITY_VALIDATION = "security_validation"
    R_EXECUTION = "r_execution"
    SLIDE_GENERATION = "slide_generation"
    EXERCISE_GENERATION = "exercise_generation"
    CONTENT_REVIEW = "content_review"
    CONTENT_REPAIR = "content_repair"
    POWERPOINT_BUILDING = "powerpoint_building"
    FINISHED = "finished"
    BLOCKED = "blocked"
    FAILED = "failed"

class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action: Action
    reason: str = Field(min_length=1)
    retry_target: Action | None = None
