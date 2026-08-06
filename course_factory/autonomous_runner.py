from __future__ import annotations

from dataclasses import dataclass, field

from .agent_dispatcher import AgentDispatcher
from .agent_result import AgentResult
from .autonomous_models import Action, Decision
from .event_bus import Event, EventBus
from .exceptions import RetryLimitExceededError
from .job_context import JobContext
from .supervisor_agent import SupervisorAgent
from .types import AgentStatus, JobStatus

@dataclass(frozen=True, slots=True)
class AutonomousRunReport:
    context: JobContext
    decisions: tuple[Decision, ...]
    iterations: int

@dataclass(slots=True)
class AutonomousRunner:
    dispatcher: AgentDispatcher
    supervisor: SupervisorAgent = field(default_factory=SupervisorAgent)
    event_bus: EventBus = field(default_factory=EventBus)
    max_iterations: int = 50
    max_retries_per_action: int = 3

    def run(self, context: JobContext) -> AutonomousRunReport:
        context = context.with_status(JobStatus.RUNNING)
        decisions: list[Decision] = []

        for iteration in range(1, self.max_iterations + 1):
            decision = self.supervisor.decide(context)
            decisions.append(decision)
            self.event_bus.emit(
                Event(
                    name="supervisor.decision",
                    source="supervisor",
                    payload={
                        "action": decision.action.value,
                        "reason": decision.reason,
                        "iteration": iteration,
                    },
                )
            )

            if decision.action is Action.FINISHED:
                return AutonomousRunReport(
                    context=context.with_status(JobStatus.COMPLETED),
                    decisions=tuple(decisions),
                    iterations=iteration,
                )

            if decision.action is Action.BLOCKED:
                return AutonomousRunReport(
                    context=context.with_status(JobStatus.BLOCKED),
                    decisions=tuple(decisions),
                    iterations=iteration,
                )

            if decision.action is Action.FAILED:
                return AutonomousRunReport(
                    context=context.with_status(JobStatus.FAILED),
                    decisions=tuple(decisions),
                    iterations=iteration,
                )

            agent = self.dispatcher.create(decision.action)
            result = self._run_agent(agent, context)
            context = context.with_result(result)

            if (
                decision.action is Action.ITERATIVE_RETRIEVAL
                and result.status is AgentStatus.SUCCESS
            ):
                updated_state = dict(context.state)
                updated_state.pop("fused_evidence", None)
                updated_state.pop("knowledge_assessment", None)
                context = context.model_copy(update={"state": updated_state})

            if (
                decision.action is Action.CONTENT_REPAIR
                and result.status is AgentStatus.SUCCESS
            ):
                updated_state = dict(context.state)
                updated_state.pop("content_review", None)
                context = context.model_copy(update={"state": updated_state})
                context = context.increment_retry(
                    Action.CONTENT_REPAIR.value,
                    maximum=self.max_retries_per_action,
                )

            if result.status is AgentStatus.SUCCESS:
                continue

            if result.status is AgentStatus.BLOCKED:
                context = context.with_status(JobStatus.BLOCKED)
                continue

            retry_key = decision.action.value
            retries = context.retry_counts.get(retry_key, 0)
            if result.status is AgentStatus.RETRY and retries < self.max_retries_per_action:
                context = context.increment_retry(
                    retry_key,
                    maximum=self.max_retries_per_action,
                )
                continue

            context = context.with_status(JobStatus.FAILED)
            return AutonomousRunReport(
                context=context,
                decisions=tuple(decisions),
                iterations=iteration,
            )

        raise RetryLimitExceededError(
            f"Autonomous runner exceeded {self.max_iterations} iterations."
        )

    def _run_agent(self, agent, context: JobContext) -> AgentResult:
        self.event_bus.emit(
            Event(
                name="agent.started",
                source=agent.name,
                payload={"job_id": context.job_id},
            )
        )
        try:
            result = agent.run(context)
        except Exception as exc:
            result = AgentResult.failed(
                agent_name=agent.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        self.event_bus.emit(
            Event(
                name="agent.finished",
                source=agent.name,
                payload={
                    "job_id": context.job_id,
                    "status": result.status.value,
                },
            )
        )
        return result
