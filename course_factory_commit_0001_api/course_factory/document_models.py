from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator

class SourceType(StrEnum):
    OFFICIAL_DOC = "official_doc"
    CRAN = "cran"
    POSIT = "posit"
    R_PROJECT = "r_project"
    BOOK = "book"
    TUTORIAL = "tutorial"
    ARTICLE = "article"
    BLOG = "blog"
    LOCAL = "local"
    OTHER = "other"

class ImportedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_type: SourceType
    topic: str = Field(min_length=1)
    content: str = Field(min_length=1)
    url: str | None = None
    language: str = "en"
    author: str | None = None
    license: str | None = None
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = "\n".join(line.rstrip() for line in value.splitlines()).strip()
        if not value:
            raise ValueError("document content cannot be empty")
        return value

class DocumentChunk(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str
    document_id: str
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

class QualityDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    score: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...]
