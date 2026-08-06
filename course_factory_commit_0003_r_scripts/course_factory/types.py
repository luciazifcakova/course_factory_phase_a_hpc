from __future__ import annotations

from enum import StrEnum
from typing import Any, TypeAlias

JsonValue: TypeAlias = Any
MetricValue: TypeAlias = int | float | str | bool
CapabilityName: TypeAlias = str

class JobStatus(StrEnum):
    PENDING="pending"; RUNNING="running"; BLOCKED="blocked"
    FAILED="failed"; COMPLETED="completed"; CANCELLED="cancelled"

class AgentStatus(StrEnum):
    SUCCESS="success"; RETRY="retry"; BLOCKED="blocked"
    FAILED="failed"; SKIPPED="skipped"

class ArtifactKind(StrEnum):
    JSON="json"; TEXT="text"; R_SCRIPT="r_script"; IMAGE="image"
    TABLE="table"; POWERPOINT="powerpoint"; LOG="log"; OTHER="other"
