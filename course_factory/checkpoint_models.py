from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field

from .graph_models import NodeExecutionRecord


class GraphCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_id: str
    completed: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    skipped: tuple[str, ...] = ()
    attempts: dict[str, int] = Field(default_factory=dict)
    outputs: dict[str, dict] = Field(default_factory=dict)
    records: tuple[NodeExecutionRecord, ...] = ()
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
