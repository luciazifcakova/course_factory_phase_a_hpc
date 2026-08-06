from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, model_validator


class NodeStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    depends_on: tuple[str, ...] = ()
    max_retries: int = Field(default=0, ge=0, le=5)
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )


class GraphDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_id: str = Field(min_length=1)
    nodes: tuple[GraphNode, ...]

    @model_validator(mode="after")
    def validate_graph(self) -> "GraphDefinition":
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("node_id values must be unique")

        known = set(ids)
        for node in self.nodes:
            unknown = set(node.depends_on) - known
            if unknown:
                raise ValueError(
                    f"Node {node.node_id!r} has unknown dependencies: "
                    f"{sorted(unknown)}"
                )
            if node.node_id in node.depends_on:
                raise ValueError(
                    f"Node {node.node_id!r} cannot depend on itself"
                )
        return self


class NodeExecutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    node_id: str
    action: str
    status: NodeStatus
    attempt: int = Field(ge=0)
    outputs: dict = Field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = Field(default=0.0, ge=0.0)


class GraphExecutionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_id: str
    records: tuple[NodeExecutionRecord, ...]
    succeeded: tuple[str, ...]
    failed: tuple[str, ...]
    skipped: tuple[str, ...]
