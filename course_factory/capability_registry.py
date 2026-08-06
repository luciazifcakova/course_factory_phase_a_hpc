from dataclasses import dataclass
from .state_machine import WorkflowStage
from .exceptions import MissingCapabilityError

@dataclass(frozen=True,slots=True)
class ExecutionPlan:
    capability:str
    factory:object
    stage:WorkflowStage
    priority:int=100
    timeout_seconds:int=900
    max_retries:int=3
    required_model:str|None=None
    required_tools:tuple[str,...]=()
    def create_agent(self):
        agent=self.factory()
        if not agent.supports(self.capability): raise TypeError("capability mismatch")
        return agent

class CapabilityRegistry:
    def __init__(self): self._plans={}
    def register(self,plan):
        self._plans.setdefault(plan.capability,[]).append(plan)
        self._plans[plan.capability].sort(key=lambda x:x.priority,reverse=True)
    def resolve(self,capability):
        if capability not in self._plans: raise MissingCapabilityError(capability)
        return self._plans[capability][0]
    def capabilities(self): return tuple(sorted(self._plans))
