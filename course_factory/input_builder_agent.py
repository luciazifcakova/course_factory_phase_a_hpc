from __future__ import annotations
from .agent import Agent
from .agent_result import AgentResult
from .course_specification import CourseSpecification
from .job_context import JobContext
from .llm_backend import LLMBackend, ensure_structured_backend
from .prompt_builder import (
    INPUT_BUILDER_PROMPT_VERSION,
    build_input_builder_prompt,
)
from .types import AgentStatus

class InputBuilderAgent(Agent):
    name = "input_builder"
    version = "1.0.0"
    capabilities = frozenset({"input_builder"})

    def __init__(self, backend: LLMBackend) -> None:
        self.backend = ensure_structured_backend(backend)

    def run(self, context: JobContext) -> AgentResult:
        attempt = context.retry_counts.get("input_builder", 0) + 1
        try:
            system, user, schema_hint = build_input_builder_prompt(context.user_request)
            spec = self.backend.generate_structured(
                CourseSpecification,
                system=system,
                user=user,
            )
        except Exception as exc:
            return AgentResult.retry(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
                attempt=min(attempt, 3),
            )

        if spec.clarification_required:
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.BLOCKED,
                outputs={"course_specification": spec.model_dump(mode="json")},
                errors=(spec.clarification_question or "Clarification required",),
                started_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
                finished_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
                attempt=min(attempt, 3),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={"course_specification": spec.model_dump(mode="json")},
            metrics={
                "input_builder_prompt_version": INPUT_BUILDER_PROMPT_VERSION,
                "learning_objective_count": len(spec.learning_objectives),
                "exercise_count": spec.exercise_count,
            },
            attempt=min(attempt, 3),
        )
