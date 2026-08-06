from __future__ import annotations

import hashlib
from pathlib import Path

from .execution_models import CollectedArtifact


class ArtifactCollector:
    """Collect supported files created under one execution workspace."""

    DEFAULT_KINDS = {
        ".png": "figure",
        ".jpg": "figure",
        ".jpeg": "figure",
        ".svg": "figure",
        ".pdf": "document",
        ".csv": "table",
        ".tsv": "table",
        ".xlsx": "spreadsheet",
        ".html": "html",
        ".json": "json",
        ".rds": "r_object",
        ".rdata": "r_workspace",
        ".txt": "text",
        ".log": "log",
    }

    def __init__(
        self,
        *,
        kinds: dict[str, str] | None = None,
    ) -> None:
        self.kinds = {
            key.lower(): value
            for key, value in (kinds or self.DEFAULT_KINDS).items()
        }

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def collect(
        self,
        *,
        workspace: str | Path,
        task_id: str,
        before: set[str] | None = None,
    ) -> tuple[CollectedArtifact, ...]:
        root = Path(workspace).resolve()
        before = before or set()
        artifacts: list[CollectedArtifact] = []

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue

            relative = path.relative_to(root).as_posix()
            if relative in before:
                continue

            kind = self.kinds.get(path.suffix.lower())
            if kind is None:
                continue

            artifacts.append(
                CollectedArtifact(
                    artifact_id=f"{task_id}:{relative}",
                    kind=kind,
                    relative_path=relative,
                    size_bytes=path.stat().st_size,
                    producer_task_id=task_id,
                    sha256=self._sha256(path),
                )
            )

        return tuple(artifacts)

    @staticmethod
    def snapshot(workspace: str | Path) -> set[str]:
        root = Path(workspace).resolve()
        return {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
