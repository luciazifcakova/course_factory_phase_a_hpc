from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .artifact_cache import ArtifactCache, CacheManager
from .artifact_manager import ArtifactManager
from .provenance_manager import ProvenanceManager


@dataclass(slots=True)
class BuildState:
    artifacts: ArtifactManager
    cache: CacheManager
    provenance: ProvenanceManager

    @classmethod
    def create(cls, workspace: str | Path) -> "BuildState":
        workspace = Path(workspace)
        return cls(
            artifacts=ArtifactManager(),
            cache=CacheManager(
                ArtifactCache(workspace / ".cache")
            ),
            provenance=ProvenanceManager(
                workspace / "provenance"
            ),
        )
