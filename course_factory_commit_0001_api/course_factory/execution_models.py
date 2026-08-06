from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExecutionRuntime(StrEnum):
    LOCAL = "local"
    APPTAINER = "apptainer"


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    script_path: str = Field(min_length=3)
    workspace: str = Field(min_length=1)
    runtime: ExecutionRuntime = ExecutionRuntime.APPTAINER
    apptainer_image: str | None = None
    expected_outputs: tuple[str, ...] = ()
    timeout_seconds: int = Field(default=900, ge=1, le=86400)
    environment: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_runtime(self) -> "ExecutionRequest":
        if self.runtime is ExecutionRuntime.APPTAINER and not self.apptainer_image:
            raise ValueError(
                "apptainer_image is required when runtime='apptainer'"
            )
        return self


class CollectedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str
    kind: str
    relative_path: str
    size_bytes: int = Field(ge=0)
    producer_task_id: str
    sha256: str = Field(min_length=64, max_length=64)


class ScriptExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    lesson_id: str
    exit_code: int
    stdout: str
    stderr: str
    runtime: ExecutionRuntime
    command: tuple[str, ...]
    duration_seconds: float = Field(ge=0.0)
    timed_out: bool = False
    expected_outputs_found: tuple[str, ...] = ()
    expected_outputs_missing: tuple[str, ...] = ()
    collected_artifacts: tuple[CollectedArtifact, ...] = ()

    @property
    def succeeded(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.expected_outputs_missing
        )


class ExecutionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    results: tuple[ScriptExecutionResult, ...]
    successful_tasks: tuple[str, ...]
    failed_tasks: tuple[str, ...]
    artifact_count: int = Field(ge=0)
