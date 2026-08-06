from __future__ import annotations

from .agent import Agent
from .agent_result import AgentResult
from .course_specification import CourseSpecification
from .job_context import JobContext
from .retriever import LocalKnowledgeRetriever, KnowledgeSufficiencyScorer

class KnowledgeRetrieverAgent(Agent):
    name = "local_knowledge_retriever"
    version = "1.0.0"
    capabilities = frozenset({"local_retrieval"})

    def __init__(
        self,
        retriever: LocalKnowledgeRetriever,
        scorer: KnowledgeSufficiencyScorer | None = None,
    ):
        self.retriever = retriever
        self.scorer = scorer or KnowledgeSufficiencyScorer()

    def run(self, context: JobContext) -> AgentResult:
        spec_raw = context.state.get("course_specification")
        if not isinstance(spec_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_specification is missing",),
            )
        try:
            spec = CourseSpecification.model_validate(spec_raw)
            query = " ".join([spec.topic, *spec.learning_objectives])
            results = self.retriever.retrieve(
                query,
                topic=spec.topic,
                limit=10,
            )
            assessment = self.scorer.assess(results)
        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "local_knowledge_results": [
                    {
                        "document_id": item.document_id,
                        "title": item.title,
                        "topic": item.topic,
                        "source": item.source,
                        "source_type": item.source_type,
                        "content": item.content,
                        "score": item.score,
                        "quality_score": item.quality_score,
                        "metadata": item.metadata,
                    }
                    for item in results
                ],
                "knowledge_assessment": {
                    "sufficient": assessment.sufficient,
                    "score": assessment.score,
                    "result_count": assessment.result_count,
                    "official_source_count": assessment.official_source_count,
                    "high_quality_count": assessment.high_quality_count,
                    "reason": assessment.reason,
                },
            },
            metrics={
                "retrieved_documents": len(results),
                "knowledge_sufficient": assessment.sufficient,
            },
        )
