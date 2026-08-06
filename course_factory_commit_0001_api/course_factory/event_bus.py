from collections import defaultdict
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field

class Event(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
    name:str; source:str; payload:dict=Field(default_factory=dict)
    timestamp:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))

class EventBus:
    def __init__(self):
        self._subscribers=defaultdict(list); self._history=[]
    def subscribe(self,name,handler): self._subscribers[name].append(handler)
    def emit(self,event):
        self._history.append(event)
        for h in tuple(self._subscribers.get(event.name,())): h(event)
    def history(self): return tuple(self._history)
