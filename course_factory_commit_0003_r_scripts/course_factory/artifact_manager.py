from __future__ import annotations

import hashlib
import json

from .artifact_graph import ArtifactGraph
from .artifact_models import ManagedArtifact


class ArtifactManager:
    def __init__(self) -> None:
        self.graph = ArtifactGraph()
        self._artifacts: dict[str, ManagedArtifact] = {}

    @staticmethod
    def checksum(payload) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def register(self, artifact: ManagedArtifact) -> ManagedArtifact:
        checksum = artifact.checksum or self.checksum(artifact.payload)
        normalized = artifact.model_copy(update={"checksum": checksum})

        self._artifacts[normalized.artifact_id] = normalized
        self.graph.add_artifact(normalized.artifact_id)

        for dependency in normalized.dependencies:
            self.graph.add_dependency(
                dependency,
                normalized.artifact_id,
            )

        return normalized

    def get(self, artifact_id: str) -> ManagedArtifact:
        return self._artifacts[artifact_id]

    def exists(self, artifact_id: str) -> bool:
        return artifact_id in self._artifacts

    def downstream(self, artifact_id: str) -> tuple[str, ...]:
        return self.graph.all_downstream(artifact_id)

    def invalidate_downstream(
        self,
        artifact_id: str,
    ) -> tuple[str, ...]:
        invalidated = self.downstream(artifact_id)
        for downstream_id in invalidated:
            self._artifacts.pop(downstream_id, None)
        return invalidated

    def all(self) -> tuple[ManagedArtifact, ...]:
        return tuple(
            self._artifacts[key]
            for key in sorted(self._artifacts)
        )
