from __future__ import annotations

from pathlib import Path

from .checkpoint_models import GraphCheckpoint
from .checkpoint_store import CheckpointStore
from .workflow_graph import WorkflowGraph


class GraphRunManifest:
    def __init__(
        self,
        graph: WorkflowGraph,
        checkpoint_store: CheckpointStore,
    ) -> None:
        self.graph = graph
        self.checkpoint_store = checkpoint_store

    def render(self) -> dict:
        if self.checkpoint_store.exists(
            self.graph.definition.graph_id
        ):
            checkpoint = self.checkpoint_store.load(
                self.graph.definition.graph_id
            )
        else:
            checkpoint = GraphCheckpoint(
                graph_id=self.graph.definition.graph_id
            )

        all_nodes = set(self.graph.nodes)
        completed = set(checkpoint.completed)
        failed = set(checkpoint.failed)
        skipped = set(checkpoint.skipped)
        pending = all_nodes - completed - failed - skipped

        return {
            "graph_id": self.graph.definition.graph_id,
            "completed": sorted(completed),
            "failed": sorted(failed),
            "skipped": sorted(skipped),
            "pending": sorted(pending),
            "attempts": checkpoint.attempts,
            "updated_at": checkpoint.updated_at.isoformat(),
        }

    def write_json(self, path: str | Path) -> Path:
        import json

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                self.render(),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return target
