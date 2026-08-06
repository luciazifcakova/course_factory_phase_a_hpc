from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field

class StageStatus(StrEnum):
    PENDING="pending"; RUNNING="running"; SUCCESS="success"; FAILED="failed"; SKIPPED="skipped"

class StageRecord(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
    name:str
    status:StageStatus=StageStatus.PENDING
    started_at:datetime|None=None
    finished_at:datetime|None=None
    retries:int=Field(default=0,ge=0,le=3)
    message:str=""

class WorkflowState(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
    current_stage:str|None=None
    stages:dict[str,StageRecord]=Field(default_factory=dict)
    history:tuple[str,...]=()
    created_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))
    updated_at:datetime=Field(default_factory=lambda:datetime.now(timezone.utc))

    def _replace(self,**changes):
        changes["updated_at"]=datetime.now(timezone.utc)
        return self.model_copy(update=changes)

    def add_stage(self,name):
        if name in self.stages:return self
        s=dict(self.stages); s[name]=StageRecord(name=name)
        return self._replace(stages=s)

    def start_stage(self,name):
        state=self.add_stage(name); s=dict(state.stages)
        s[name]=s[name].model_copy(update={"status":StageStatus.RUNNING,
                                           "started_at":datetime.now(timezone.utc)})
        return state._replace(current_stage=name,stages=s,history=(*state.history,f"START {name}"))

    def finish_stage(self,name,success,message=""):
        s=dict(self.stages)
        s[name]=s[name].model_copy(update={"status":StageStatus.SUCCESS if success else StageStatus.FAILED,
                                           "finished_at":datetime.now(timezone.utc),"message":message})
        return self._replace(current_stage=None,stages=s,
                             history=(*self.history,f"FINISH {name}"))
