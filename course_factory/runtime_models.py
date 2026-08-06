from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field


class RuntimeKind(StrEnum):
    LOCAL = "local"
    SLURM = "slurm"


class ResourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cpus: int = Field(default=1, ge=1, le=256)
    memory_gb: int = Field(default=2, ge=1, le=2048)
    time_minutes: int = Field(default=30, ge=1, le=10080)
    gpus: int = Field(default=0, ge=0, le=16)
    partition: str | None = None


class RuntimeTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    command: tuple[str, ...]
    working_directory: str
    environment: dict[str, str] = Field(default_factory=dict)
    resources: ResourceRequest = Field(default_factory=ResourceRequest)
    runtime: RuntimeKind = RuntimeKind.LOCAL
    stdout_path: str | None = None
    stderr_path: str | None = None


class RuntimeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    runtime: RuntimeKind
    return_code: int
    stdout: str
    stderr: str
    external_job_id: str | None = None
    submitted: bool = False
    completed: bool = False
    duration_seconds: float = Field(default=0.0, ge=0.0)

    @property
    def succeeded(self) -> bool:
        return self.completed and self.return_code == 0
