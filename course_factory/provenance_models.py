from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field


class ProvenanceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str
    artifact_type: str
    agent_name: str
    agent_version: str
    llm_model: str | None = None
    prompt_checksum: str
    input_checksums: tuple[str, ...]
    output_checksum: str
    parent_artifacts: tuple[str, ...]
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
