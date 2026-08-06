from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .runtime_models import RuntimeKind, RuntimeResult


class ExecutedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: str
    absolute_path: str
    size_bytes: int = Field(ge=0)
    sha256: str


class CourseScriptExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    lesson_id: str
    runtime_result: RuntimeResult
    expected_outputs_found: tuple[str, ...] = ()
    expected_outputs_missing: tuple[str, ...] = ()
    outputs: tuple[ExecutedOutput, ...] = ()

    @property
    def succeeded(self) -> bool:
        return (
            self.runtime_result.succeeded
            and not self.expected_outputs_missing
        )


class CourseExecutionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    executor: RuntimeKind
    results: tuple[CourseScriptExecution, ...]
    successful_task_ids: tuple[str, ...]
    failed_task_ids: tuple[str, ...]
    output_count: int = Field(ge=0)

    @property
    def succeeded(self) -> bool:
        return not self.failed_task_ids
