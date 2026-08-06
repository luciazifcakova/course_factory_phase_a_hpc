from __future__ import annotations

from .agent import Agent
from .agent_result import AgentResult
from .document_deduplicator import DocumentDeduplicator
from .document_quality_filter import DocumentQualityFilter
from .evidence_models import KnowledgeAssessment
from .job_context import JobContext
from .retrieval_models import (
    IterativeRetrievalReport,
    RetrievalSource,
)
from .retrieval_planner import RetrievalPlanner
from .search_backend import SearchBackend


class IterativeRetrievalAgent(Agent):
    name = "iterative_retrieval"
    version = "1.0.0"
    capabilities = frozenset({"iterative_retrieval"})

    def __init__(
        self,
        *,
        backend: SearchBackend,
        source: RetrievalSource = RetrievalSource.WEB,
        planner: RetrievalPlanner | None = None,
        quality_filter: DocumentQualityFilter | None = None,
        deduplicator: DocumentDeduplicator | None = None,
    ) -> None:
        self.backend = backend
        self.source = source
        self.planner = planner or RetrievalPlanner()
        self.quality_filter = quality_filter or DocumentQualityFilter()
        self.deduplicator = deduplicator or DocumentDeduplicator()

    def run(self, context: JobContext) -> AgentResult:
        assessment_raw = context.state.get("knowledge_assessment")
        if not isinstance(assessment_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("knowledge_assessment is missing",),
            )

        try:
            assessment = KnowledgeAssessment.model_validate(
                assessment_raw
            )
            tasks = self.planner.build(
                assessment,
                source=self.source,
            )

            gathered = []
            for task in tasks:
                gathered.extend(self.backend.search(task))

            filtered = self.quality_filter.filter(tuple(gathered))
            unique, duplicate_count = self.deduplicator.deduplicate(
                filtered
            )

            report = IterativeRetrievalReport(
                tasks=tasks,
                results=unique,
                query_count=len(tasks),
                result_count=len(unique),
                duplicate_count=duplicate_count,
            )

            existing = context.state.get(
                "local_knowledge_results",
                [],
            )
            if not isinstance(existing, list):
                existing = []

            merged = [
                *existing,
                *[
                    {
                        "document_id": result.result_id,
                        "title": result.title,
                        "topic": result.topic,
                        "source": result.url or result.source.value,
                        "source_type": result.source_type,
                        "content": result.content,
                        "score": result.quality_score,
                        "quality_score": result.quality_score,
                        "metadata": {
                            **result.metadata,
                            "retrieval_query": result.query,
                        },
                    }
                    for result in unique
                ],
            ]
        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "iterative_retrieval_report": report.model_dump(
                    mode="json"
                ),
                "local_knowledge_results": merged,
            },
            metrics={
                "iterative_retrieval_queries": report.query_count,
                "iterative_retrieval_results": report.result_count,
                "iterative_retrieval_duplicates": report.duplicate_count,
            },
        )
