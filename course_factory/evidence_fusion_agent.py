from __future__ import annotations
from collections import Counter
from .agent import Agent
from .agent_result import AgentResult
from .evidence_models import FusedEvidenceSet
from .job_context import JobContext
from .llm_backend import LLMBackend

FUSION_SCHEMA = '{"topics":[{"topic":"string","summary":"string","supporting_documents":["DOC-1"],"conflicting_documents":[],"confidence":0.9,"unresolved_questions":[]}],"source_document_count":1,"unique_document_count":1,"duplicate_document_ids":[]}'

class EvidenceFusionAgent(Agent):
    name = "evidence_fusion"
    version = "1.0.0"
    capabilities = frozenset({"evidence_fusion"})

    def __init__(self, backend: LLMBackend):
        self.backend = backend

    def run(self, context: JobContext) -> AgentResult:
        evidence = context.state.get("local_knowledge_results")
        if not isinstance(evidence, list):
            return AgentResult.failed(agent_name=self.name, errors=("local_knowledge_results is missing",))
        try:
            document_ids = [
                str(item.get("document_id"))
                for item in evidence
                if isinstance(item, dict) and item.get("document_id")
            ]
            counts = Counter(document_ids)
            duplicates = tuple(sorted(k for k, v in counts.items() if v > 1))
            response = self.backend.generate_json(
                system="Fuse validated evidence, merge duplicates, preserve document IDs, identify conflicts, and never invent facts.",
                user=f"RETRIEVED EVIDENCE:\n{evidence}",
                schema_hint=FUSION_SCHEMA,
            )
            fused = FusedEvidenceSet.model_validate(response).model_copy(update={
                "source_document_count": len(evidence),
                "unique_document_count": len(set(document_ids)),
                "duplicate_document_ids": duplicates,
            })
        except Exception as exc:
            return AgentResult.failed(agent_name=self.name, errors=(f"{type(exc).__name__}: {exc}",))
        return AgentResult.success(
            agent_name=self.name,
            outputs={"fused_evidence": fused.model_dump(mode="json")},
            metrics={
                "fused_topic_count": len(fused.topics),
                "source_document_count": fused.source_document_count,
                "unique_document_count": fused.unique_document_count,
                "duplicate_document_count": len(fused.duplicate_document_ids),
            },
        )
