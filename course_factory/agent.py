from abc import ABC, abstractmethod
from .job_context import JobContext
from .agent_result import AgentResult

class Agent(ABC):
    name:str
    version:str="1.0.0"
    capabilities:frozenset[str]=frozenset()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls is Agent: return
        if not getattr(cls,"name",""): raise TypeError("name required")
        if not getattr(cls,"capabilities",frozenset()): raise TypeError("capabilities required")

    @abstractmethod
    def run(self,context:JobContext)->AgentResult: raise NotImplementedError
    def supports(self,capability): return capability in self.capabilities
