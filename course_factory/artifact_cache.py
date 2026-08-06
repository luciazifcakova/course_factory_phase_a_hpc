from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactCache:
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, artifact_id: str) -> str:
        return artifact_id.replace("/", "__").replace(":", "__")

    def path(self, artifact_id: str) -> Path:
        return self.cache_dir / f"{self._safe_name(artifact_id)}.json"

    def exists(self, artifact_id: str) -> bool:
        return self.path(artifact_id).is_file()

    def save(
        self,
        artifact_id: str,
        *,
        checksum: str,
        payload: Any,
        metadata: dict | None = None,
    ) -> Path:
        target = self.path(artifact_id)
        target.write_text(
            json.dumps(
                {
                    "artifact_id": artifact_id,
                    "checksum": checksum,
                    "payload": payload,
                    "metadata": metadata or {},
                },
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )
        return target

    def load(self, artifact_id: str) -> dict:
        return json.loads(
            self.path(artifact_id).read_text(encoding="utf-8")
        )

    def delete(self, artifact_id: str) -> None:
        self.path(artifact_id).unlink(missing_ok=True)


class CacheManager:
    def __init__(self, cache: ArtifactCache) -> None:
        self.cache = cache

    def should_execute(
        self,
        artifact_id: str,
        checksum: str,
    ) -> bool:
        if not self.cache.exists(artifact_id):
            return True
        cached = self.cache.load(artifact_id)
        return cached.get("checksum") != checksum

    def restore(self, artifact_id: str):
        if not self.cache.exists(artifact_id):
            raise KeyError(artifact_id)
        return self.cache.load(artifact_id)["payload"]

    def update(
        self,
        artifact_id: str,
        *,
        checksum: str,
        payload,
        metadata: dict | None = None,
    ) -> Path:
        return self.cache.save(
            artifact_id,
            checksum=checksum,
            payload=payload,
            metadata=metadata,
        )
