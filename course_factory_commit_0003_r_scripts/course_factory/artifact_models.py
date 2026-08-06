from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field


class ManagedArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    version: int = Field(default=1, ge=1)
    checksum: str | None = None
    created_by: str = Field(min_length=1)
    dependencies: tuple[str, ...] = ()
    payload: dict | list | str | int | float | bool | None = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
