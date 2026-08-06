from __future__ import annotations

import json
from pathlib import Path

from .checkpoint_models import GraphCheckpoint


class CheckpointStore:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, graph_id: str) -> Path:
        safe = graph_id.replace("/", "__").replace(":", "__")
        return self.directory / f"{safe}.checkpoint.json"

    def exists(self, graph_id: str) -> bool:
        return self._path(graph_id).is_file()

    def save(self, checkpoint: GraphCheckpoint) -> Path:
        target = self._path(checkpoint.graph_id)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            checkpoint.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)
        return target

    def load(self, graph_id: str) -> GraphCheckpoint:
        return GraphCheckpoint.model_validate_json(
            self._path(graph_id).read_text(encoding="utf-8")
        )

    def delete(self, graph_id: str) -> None:
        self._path(graph_id).unlink(missing_ok=True)
