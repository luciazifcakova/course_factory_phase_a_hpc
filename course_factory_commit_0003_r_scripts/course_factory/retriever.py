from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .embedding_service import EmbeddingService
from .knowledge_store import KnowledgeStore
from .vector_store import VectorStore

@dataclass(frozen=True, slots=True)
class RetrievalResult:
    document_id: str
    title: str
    topic: str
    source: str
    source_type: str
    content: str
    score: float
    quality_score: float
    metadata: dict[str, Any]

@dataclass(frozen=True, slots=True)
class KnowledgeAssessment:
    sufficient: bool
    score: float
    result_count: int
    official_source_count: int
    high_quality_count: int
    reason: str

class LocalKnowledgeRetriever:
    def __init__(
        self,
        *,
        metadata_store: KnowledgeStore,
        vector_store: VectorStore,
        embeddings: EmbeddingService,
    ):
        self.metadata_store = metadata_store
        self.vector_store = vector_store
        self.embeddings = embeddings

    def index_document(
        self,
        *,
        document_id: str,
        title: str,
        source: str,
        source_type: str,
        topic: str,
        content: str,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
        quality_score: float = 1.0,
    ) -> tuple[int, bool]:
        row_id, inserted = self.metadata_store.insert(
            document_id=document_id,
            title=title,
            source=source,
            source_type=source_type,
            topic=topic,
            content=content,
            url=url,
            metadata=metadata,
            quality_score=quality_score,
        )
        if inserted:
            vector = self.embeddings.embed_document(title, content)
            self.vector_store.upsert(
                item_id=document_id,
                embedding=vector,
                metadata={
                    "topic": topic,
                    "source_type": source_type,
                    "quality_score": quality_score,
                },
                document=content,
            )
        return row_id, inserted

    def retrieve(
        self,
        query: str,
        *,
        topic: str | None = None,
        limit: int = 10,
    ) -> list[RetrievalResult]:
        vector = self.embeddings.embed_query(query)
        where = {"topic": topic} if topic else None
        matches = self.vector_store.search(
            embedding=vector,
            limit=limit,
            where=where,
        )
        results: list[RetrievalResult] = []
        for match in matches:
            doc = self.metadata_store.get_by_document_id(match["id"])
            if not doc:
                continue
            similarity = max(0.0, 1.0 - float(match["distance"]))
            quality = float(doc["quality_score"])
            score = 0.8 * similarity + 0.2 * quality
            results.append(
                RetrievalResult(
                    document_id=doc["document_id"],
                    title=doc["title"],
                    topic=doc["topic"],
                    source=doc["source"],
                    source_type=doc["source_type"],
                    content=doc["content"],
                    score=score,
                    quality_score=quality,
                    metadata=doc["metadata"],
                )
            )
        return sorted(results, key=lambda item: item.score, reverse=True)

class KnowledgeSufficiencyScorer:
    OFFICIAL_TYPES = {"official_doc", "cran", "posit", "r_project"}

    def __init__(
        self,
        *,
        minimum_results: int = 3,
        minimum_official_sources: int = 1,
        minimum_score: float = 0.70,
        minimum_quality: float = 0.75,
    ):
        self.minimum_results = minimum_results
        self.minimum_official_sources = minimum_official_sources
        self.minimum_score = minimum_score
        self.minimum_quality = minimum_quality

    def assess(self, results: list[RetrievalResult]) -> KnowledgeAssessment:
        if not results:
            return KnowledgeAssessment(
                sufficient=False,
                score=0.0,
                result_count=0,
                official_source_count=0,
                high_quality_count=0,
                reason="No local knowledge matched the request.",
            )

        official = sum(
            1 for result in results if result.source_type in self.OFFICIAL_TYPES
        )
        high_quality = sum(
            1
            for result in results
            if result.quality_score >= self.minimum_quality
            and result.score >= self.minimum_score
        )
        coverage = min(1.0, len(results) / self.minimum_results)
        official_component = min(
            1.0, official / max(1, self.minimum_official_sources)
        )
        quality_component = min(
            1.0, high_quality / max(1, self.minimum_results)
        )
        total = 0.4 * coverage + 0.3 * official_component + 0.3 * quality_component
        sufficient = (
            len(results) >= self.minimum_results
            and official >= self.minimum_official_sources
            and high_quality >= self.minimum_results
        )
        reason = (
            "Local knowledge is sufficient."
            if sufficient
            else (
                f"Insufficient local knowledge: {len(results)} result(s), "
                f"{official} official source(s), {high_quality} high-quality result(s)."
            )
        )
        return KnowledgeAssessment(
            sufficient=sufficient,
            score=total,
            result_count=len(results),
            official_source_count=official,
            high_quality_count=high_quality,
            reason=reason,
        )
