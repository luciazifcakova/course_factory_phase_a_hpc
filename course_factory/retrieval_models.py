from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class RetrievalSource(StrEnum):
    LOCAL = "local"
    WEB = "web"


class RetrievalTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str = Field(min_length=1)
    query: str = Field(min_length=3)
    source: RetrievalSource
    priority: int = Field(default=100, ge=1, le=1000)
    topic: str | None = None
    limit: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    result_id: str = Field(min_length=1)
    query: str
    title: str = Field(min_length=1)
    url: str | None = None
    source: RetrievalSource
    source_type: str = "other"
    topic: str
    content: str = Field(min_length=1)
    quality_score: float = Field(ge=0.0, le=1.0)
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )


class IterativeRetrievalReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tasks: tuple[RetrievalTask, ...]
    results: tuple[SearchResult, ...]
    query_count: int = Field(ge=0)
    result_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
