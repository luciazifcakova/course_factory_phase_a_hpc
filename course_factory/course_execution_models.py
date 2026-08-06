from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .runtime_models import RuntimeKind, RuntimeResult


class ExecutedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relative_path: str
    absolute_path: str
    size_bytes: int = Field(ge=0)
    sha256: str


class ScriptExecutionAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt: int = Field(ge=1)
    repaired: bool = False
    script_path: str
    runtime_result: RuntimeResult
    expected_outputs_found: tuple[str, ...] = ()
    expected_outputs_missing: tuple[str, ...] = ()
    repair_request_path: str | None = None
    repair_response_path: str | None = None
    repair_validation_errors: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return (
            self.runtime_result.succeeded
            and not self.expected_outputs_missing
        )


class CourseScriptExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    lesson_id: str
    runtime_result: RuntimeResult
    expected_outputs_found: tuple[str, ...] = ()
    expected_outputs_missing: tuple[str, ...] = ()
    outputs: tuple[ExecutedOutput, ...] = ()
    attempts: tuple[ScriptExecutionAttempt, ...] = ()
    final_script_path: str
    repair_count: int = Field(default=0, ge=0)

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
    repair_attempt_count: int = Field(default=0, ge=0)
    repaired_task_ids: tuple[str, ...] = ()

    @property
    def succeeded(self) -> bool:
        return not self.failed_task_ids
