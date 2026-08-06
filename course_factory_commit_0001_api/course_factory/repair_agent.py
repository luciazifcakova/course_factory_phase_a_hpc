from __future__ import annotations
from .agent import Agent
from .agent_result import AgentResult
from .job_context import JobContext
from .llm_backend import LLMBackend
from .review_models import ReviewReport, RepairResult

REPAIR_SCHEMA = '{"artifact_name":"slide_deck","repaired_payload":{},"change_summary":["string"],"attempt":1}'

class RepairAgent(Agent):
    name = "content_repair"
    capabilities = frozenset({"content_repair"})

    def __init__(self, backend: LLMBackend):
        self.backend = backend

    def _repair(self, artifact_name, payload, report, attempt):
        response = self.backend.generate_json(
            system=(
                "Repair the course artifact using the review issues. "
                "Preserve IDs, citations, technical meaning, and schema shape."
            ),
            user=str({
                "artifact_name": artifact_name,
                "payload": payload,
                "review": report.model_dump(mode="json"),
                "attempt": attempt,
            }),
            schema_hint=REPAIR_SCHEMA,
        )
        return RepairResult.model_validate(response)

    def run(self, context: JobContext) -> AgentResult:
        review = context.state.get("content_review")
        slides = context.state.get("slide_deck")
        exercises = context.state.get("exercise_set")
        if not all(isinstance(x, dict) for x in (review, slides, exercises)):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("review or generated artifacts are missing",),
            )

        attempt = context.retry_counts.get("content_repair", 0) + 1
        outputs = {}
        summaries = []

        slide_report = ReviewReport.model_validate(review["slide_deck"])
        exercise_report = ReviewReport.model_validate(review["exercise_set"])

        if not slide_report.passed:
            result = self._repair("slide_deck", slides, slide_report, attempt)
            outputs["slide_deck"] = result.repaired_payload
            summaries.extend(result.change_summary)

        if not exercise_report.passed:
            result = self._repair("exercise_set", exercises, exercise_report, attempt)
            outputs["exercise_set"] = result.repaired_payload
            summaries.extend(result.change_summary)

        outputs["content_repair_report"] = {
            "attempt": attempt,
            "updated_artifacts": sorted(k for k in outputs if k != "content_repair_report"),
            "change_summary": summaries,
        }
        return AgentResult.success(
            agent_name=self.name,
            outputs=outputs,
            metrics={"repaired_artifact_count": len(outputs)-1},
        )
