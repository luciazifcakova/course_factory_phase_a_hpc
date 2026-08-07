from __future__ import annotations

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class RCodeLLMResponse(BaseModel):
    '''
    Validated response returned by the LLM for one R-script task.

    `script` and `r_script` are accepted as compatibility aliases because
    local models occasionally use those names despite an explicit schema.
    Every downstream stage receives the canonical `code` attribute.
    '''

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    code: str = Field(
        min_length=1,
        validation_alias=AliasChoices(
            "code",
            "script",
            "r_script",
        ),
    )
    expected_outputs: tuple[str, ...] = ()
    knowledge_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def normalize_code(self) -> "RCodeLLMResponse":
        code = self.code.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            if lines and lines[0].strip().lower() in {
                "```",
                "```r",
                "```rscript",
            }:
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code = "\n".join(lines).strip()

        if not code:
            raise ValueError("Generated R code is empty.")

        return self.model_copy(update={"code": code})


class RCodeGenerationAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    attempt: int = Field(ge=1)
    succeeded: bool
    request_path: str
    response_path: str | None = None
    validation_errors: tuple[str, ...] = ()


class RScriptArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=3)
    code: str = Field(min_length=1)
    required_packages: tuple[str, ...] = ()
    # LLM-declared concrete outputs are provenance only.
    expected_outputs: tuple[str, ...] = ()
    # Immutable workflow-planner contracts define execution success.
    output_contracts: tuple[str, ...] = ()
    knowledge_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_path(self) -> "RScriptArtifact":
        if not self.relative_path.endswith(".R"):
            raise ValueError("relative_path must end with .R")
        return self


class RCodeGenerationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scripts: tuple[RScriptArtifact, ...]
    generated_count: int = Field(ge=0)
    failed_task_ids: tuple[str, ...] = ()
    failure_reasons: dict[str, tuple[str, ...]] = Field(
        default_factory=dict
    )
    attempts: tuple[RCodeGenerationAttempt, ...] = ()
