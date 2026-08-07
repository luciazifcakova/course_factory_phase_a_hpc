from __future__ import annotations
from .agent import Agent
from .agent_result import AgentResult
from .course_specification import CourseSpecification
from .evidence_models import FusedEvidenceSet, KnowledgeAssessment
from .job_context import JobContext
from .llm_backend import LLMBackend, ensure_structured_backend

ASSESSMENT_SCHEMA = '{"sufficient":true,"confidence":0.9,"covered_topics":["string"],"missing_topics":[],"suggested_queries":[],"explanation":"string"}'

class KnowledgeAssessmentAgent(Agent):
    name = "knowledge_assessment"
    version = "1.0.0"
    capabilities = frozenset({"knowledge_assessment"})

    def __init__(self, backend: LLMBackend):
        self.backend = ensure_structured_backend(backend)

    def run(self, context: JobContext) -> AgentResult:
        spec_raw = context.state.get("course_specification")
        fused_raw = context.state.get("fused_evidence")
        if not isinstance(spec_raw, dict):
            return AgentResult.failed(agent_name=self.name, errors=("course_specification is missing",))
        if not isinstance(fused_raw, dict):
            return AgentResult.failed(agent_name=self.name, errors=("fused_evidence is missing",))
        try:
            spec = CourseSpecification.model_validate(spec_raw)
            fused = FusedEvidenceSet.model_validate(fused_raw)
            assessment = self.backend.generate_structured(
                KnowledgeAssessment,
                system="Assess whether evidence covers every learning objective and requested package. Never mark sufficient when a core topic lacks support. Propose specific queries when insufficient.",
                user=f"COURSE:\n{spec.model_dump_json(indent=2)}\n\nEVIDENCE:\n{fused.model_dump_json(indent=2)}",
            )
        except Exception as exc:
            return AgentResult.failed(agent_name=self.name, errors=(f"{type(exc).__name__}: {exc}",))
        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "knowledge_assessment": assessment.model_dump(mode="json"),
                "knowledge_search_queries": list(assessment.suggested_queries),
            },
            metrics={
                "knowledge_sufficient": assessment.sufficient,
                "knowledge_confidence": assessment.confidence,
                "missing_topic_count": len(assessment.missing_topics),
                "suggested_query_count": len(assessment.suggested_queries),
            },
        )
