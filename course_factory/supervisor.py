from dataclasses import dataclass, field
from .agent_result import AgentResult
from .event_bus import Event, EventBus
from .state_machine import StateMachine, WorkflowStage
from .workflow_state import WorkflowState
from .types import AgentStatus, JobStatus
from .exceptions import RetryLimitExceededError

@dataclass(slots=True)
class SupervisorRun:
    context:object
    workflow:WorkflowState

@dataclass(slots=True)
class Supervisor:
    registry:object
    state_machine:StateMachine=field(default_factory=StateMachine)
    event_bus:EventBus=field(default_factory=EventBus)

    def initialize(self,context):
        self.event_bus.emit(Event(name="workflow.started",source="supervisor"))
        return SupervisorRun(context.with_status(JobStatus.RUNNING),
                             self.state_machine.start(WorkflowState()))

    def execute_plan(self,run,plan):
        source=WorkflowStage(run.workflow.current_stage)
        workflow=self.state_machine.transition(run.workflow,source,plan.stage,
                                               f"Executing {plan.capability}")
        context=run.context.with_capability(plan.capability)
        for attempt in range(1,plan.max_retries+1):
            agent=plan.create_agent()
            try: result=agent.run(context)
            except Exception as exc:
                result=AgentResult.failed(agent_name=agent.name,
                                          errors=(f"{type(exc).__name__}: {exc}",),
                                          attempt=attempt)
            context=context.with_result(result)
            if result.status is AgentStatus.SUCCESS:
                return SupervisorRun(context,workflow)
            if result.status is AgentStatus.RETRY and attempt<plan.max_retries:
                context=context.increment_retry(plan.capability,plan.max_retries)
                continue
            raise RetryLimitExceededError(plan.capability)
        raise RetryLimitExceededError(plan.capability)

    def run(self,context,capabilities):
        run=self.initialize(context)
        for capability in capabilities:
            run=self.execute_plan(run,self.registry.resolve(capability))
        source=WorkflowStage(run.workflow.current_stage)
        workflow=self.state_machine.transition(run.workflow,source,WorkflowStage.COMPLETED,"done")
        return SupervisorRun(run.context.with_status(JobStatus.COMPLETED).with_capability(None),workflow)
