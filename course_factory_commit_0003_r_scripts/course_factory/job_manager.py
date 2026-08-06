from __future__ import annotations

from pathlib import Path
from typing import Any

from .job_store import SQLiteJobStore
from .workspace_manager import WorkspaceManager


class JobManager:
    def __init__(
        self,
        *,
        store: SQLiteJobStore,
        workspace: WorkspaceManager,
    ) -> None:
        self.store = store
        self.workspace = workspace

    def create(
        self,
        *,
        job_id: str,
        request: dict[str, Any],
    ) -> Path:
        self.workspace.initialize()
        directory = self.workspace.job_directory(job_id)
        self.store.create_job(
            job_id=job_id,
            request=request,
            state={
                "job_directory": str(directory),
            },
        )
        self.event(
            job_id=job_id,
            step="initialization",
            message="Course-generation job created.",
            payload={"job_directory": str(directory)},
        )
        return directory

    def transition(
        self,
        *,
        job_id: str,
        status: str,
        step: str,
        patch: dict[str, Any] | None = None,
        message: str | None = None,
        level: str = "INFO",
    ) -> None:
        self.store.update_job(
            job_id=job_id,
            status=status,
            current_step=step,
            patch=patch,
        )
        if message:
            self.event(
                job_id=job_id,
                step=step,
                message=message,
                level=level,
                payload=patch,
            )

    def event(
        self,
        *,
        job_id: str,
        step: str,
        message: str,
        level: str = "INFO",
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.store.add_event(
            job_id=job_id,
            step=step,
            message=message,
            level=level,
            payload=payload,
        )

    def status(self, job_id: str) -> dict[str, Any]:
        return self.store.get_job(job_id)

    def events(self, job_id: str) -> list[dict[str, Any]]:
        return self.store.list_events(job_id)
