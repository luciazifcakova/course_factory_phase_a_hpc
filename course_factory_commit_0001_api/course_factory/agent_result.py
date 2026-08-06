from __future__ import annotations
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .types import AgentStatus, CapabilityName, JsonValue, MetricValue

class AgentResult(BaseModel):
    model_config=ConfigDict(extra="forbid", frozen=True)
    agent_name:str=Field(min_length=1)
    status:AgentStatus
    outputs:dict[str,JsonValue]=Field(default_factory=dict)
    warnings:tuple[str,...]=()
    errors:tuple[str,...]=()
    metrics:dict[str,MetricValue]=Field(default_factory=dict)
    emitted_events:tuple[str,...]=()
    next_capabilities:tuple[CapabilityName,...]=()
    started_at:datetime
    finished_at:datetime
    attempt:int=Field(default=1,ge=1,le=3)

    @model_validator(mode="after")
    def valid(self):
        if self.finished_at < self.started_at: raise ValueError("invalid timestamps")
        if self.status is AgentStatus.SUCCESS and self.errors:
            raise ValueError("success cannot contain errors")
        if self.status is AgentStatus.FAILED and not self.errors:
            raise ValueError("failure requires errors")
        return self

    @classmethod
    def success(cls, *, agent_name, outputs=None, metrics=None, attempt=1):
        now=datetime.now(timezone.utc)
        return cls(agent_name=agent_name,status=AgentStatus.SUCCESS,
                   outputs=outputs or {},metrics=metrics or {},
                   started_at=now,finished_at=now,attempt=attempt)

    @classmethod
    def retry(cls, *, agent_name, errors, attempt):
        now=datetime.now(timezone.utc)
        return cls(agent_name=agent_name,status=AgentStatus.RETRY,errors=errors,
                   started_at=now,finished_at=now,attempt=attempt)

    @classmethod
    def failed(cls, *, agent_name, errors, attempt=1):
        now=datetime.now(timezone.utc)
        return cls(agent_name=agent_name,status=AgentStatus.FAILED,errors=errors,
                   started_at=now,finished_at=now,attempt=attempt)
