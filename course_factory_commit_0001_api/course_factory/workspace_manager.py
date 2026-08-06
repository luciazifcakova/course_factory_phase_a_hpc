from __future__ import annotations

import re
from pathlib import Path


def safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or "unnamed"


class WorkspaceManager:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def initialize(self) -> None:
        for relative in (
            "state",
            "jobs",
            "knowledge/inbox",
            "knowledge/index",
            "cache/web",
            "presentations",
        ):
            (self.root / relative).mkdir(
                parents=True,
                exist_ok=True,
            )

    def job_directory(self, job_id: str) -> Path:
        path = self.root / "jobs" / safe_identifier(job_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def task_directory(
        self,
        *,
        job_id: str,
        task_id: str,
    ) -> Path:
        path = (
            self.job_directory(job_id)
            / "tasks"
            / safe_identifier(task_id)
        )
        path.mkdir(parents=True, exist_ok=True)
        for relative in ("output", "home", "tmp", "logs"):
            (path / relative).mkdir(exist_ok=True)
        return path
