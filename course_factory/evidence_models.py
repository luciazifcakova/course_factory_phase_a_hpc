from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator

class FusedEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    topic: str = Field(min_length=1)
    summary: str = Field(min_length=10)
    supporting_documents: tuple[str, ...]
    conflicting_documents: tuple[str, ...] = ()
    confidence: float = Field(ge=0.0, le=1.0)
    unresolved_questions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_documents(self):
        overlap = set(self.supporting_documents) & set(self.conflicting_documents)
        if overlap:
            raise ValueError(f"Documents cannot both support and conflict: {sorted(overlap)}")
        return self

class FusedEvidenceSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    topics: tuple[FusedEvidenceItem, ...]
    source_document_count: int = Field(ge=0)
    unique_document_count: int = Field(ge=0)
    duplicate_document_ids: tuple[str, ...] = ()

class KnowledgeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    sufficient: bool
    confidence: float = Field(ge=0.0, le=1.0)
    covered_topics: tuple[str, ...] = ()
    missing_topics: tuple[str, ...] = ()
    suggested_queries: tuple[str, ...] = ()
    explanation: str = Field(min_length=10)

    @model_validator(mode="after")
    def validate_queries(self):
        if not self.sufficient and not self.suggested_queries:
            raise ValueError("suggested_queries required when knowledge is insufficient")
        return self
