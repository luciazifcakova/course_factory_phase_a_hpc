from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from typing import Self
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator
from .agent_result import AgentResult
from .types import ArtifactKind, JsonValue, JobStatus, MetricValue

class ArtifactRef(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
    artifact_id:str; kind:ArtifactKind; path:str; producer:str
    metadata:dict[str,JsonValue]=Field(default_factory=dict)

    @field_validator("path")
    @classmethod
    def relative(cls,value):
        p=Path(value)
        if p.is_absolute() or ".." in p.parts: raise ValueError("path must be relative")
        return value

class JobContext(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
    job_id:str
    user_request:str=Field(min_length=2)
    status:JobStatus=JobStatus.PENDING
    current_capability:str|None=None
    created_at:datetime
    updated_at:datetime
    config:dict[str,JsonValue]=Field(default_factory=dict)
    state:dict[str,JsonValue]=Field(default_factory=dict)
    metrics:dict[str,MetricValue]=Field(default_factory=dict)
    artifacts:tuple[ArtifactRef,...]=()
    results:tuple[AgentResult,...]=()
    retry_counts:dict[str,int]=Field(default_factory=dict)

    @classmethod
    def create(cls, *, user_request, config=None, job_id=None):
        now=datetime.now(timezone.utc)
        return cls(job_id=job_id or f"job_{uuid4().hex}",user_request=user_request,
                   created_at=now,updated_at=now,config=config or {})

    def _replace(self, **changes)->Self:
        changes["updated_at"]=datetime.now(timezone.utc)
        return self.model_copy(update=changes)

    def with_status(self,status)->Self: return self._replace(status=status)
    def with_capability(self,capability)->Self: return self._replace(current_capability=capability)

    def with_result(self,result)->Self:
        s=dict(self.state); s.update(result.outputs)
        m=dict(self.metrics); m.update(result.metrics)
        return self._replace(results=(*self.results,result),state=s,metrics=m)

    def increment_retry(self, capability, maximum=3)->Self:
        current=self.retry_counts.get(capability,0)
        if current>=maximum: raise ValueError("retry limit reached")
        r=dict(self.retry_counts); r[capability]=current+1
        return self._replace(retry_counts=r)
