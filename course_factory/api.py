from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import yaml

from .course_request_models import CreateCourseRequest
from .course_response_models import CreateCourseResponse
from .hpc_settings import HPCSettings
from .job_manager import JobManager
from .job_store import SQLiteJobStore
from .llm_backend import LLMBackend, OllamaBackend
from .pipeline_runner import PipelineRunner
from .workspace_manager import WorkspaceManager


class CourseFactoryAPI:
    def __init__(
        self,
        *,
        settings: HPCSettings,
        backend: LLMBackend | None = None,
    ) -> None:
        workspace = WorkspaceManager(settings.workspace)
        workspace.initialize()

        store = SQLiteJobStore(
            settings.workspace / "state" / "jobs.sqlite3"
        )
        self.jobs = JobManager(
            store=store,
            workspace=workspace,
        )
        self.backend = backend or OllamaBackend(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )
        self.runner = PipelineRunner(
            backend=self.backend,
            jobs=self.jobs,
        )

    def create_course(
        self,
        request: CreateCourseRequest | str,
        *,
        job_id: str | None = None,
    ) -> CreateCourseResponse:
        normalized = (
            CreateCourseRequest(prompt=request)
            if isinstance(request, str)
            else request
        )
        resolved_job_id = job_id or f"job_{uuid4().hex}"
        self.jobs.create(
            job_id=resolved_job_id,
            request=normalized.model_dump(mode="json"),
        )
        return self.runner.run(
            job_id=resolved_job_id,
            request=normalized,
        )

    def create_course_from_yaml(
        self,
        path: str | Path,
        *,
        job_id: str | None = None,
    ) -> CreateCourseResponse:
        source = Path(path)
        payload = yaml.safe_load(
            source.read_text(encoding="utf-8")
        )
        if isinstance(payload, str):
            request = CreateCourseRequest(prompt=payload)
        elif isinstance(payload, dict):
            request = CreateCourseRequest.model_validate(payload)
        else:
            raise ValueError(
                "Course request YAML must contain text or a mapping."
            )

        return self.create_course(
            request,
            job_id=job_id,
        )

    def get_job(self, job_id: str) -> dict:
        return self.jobs.status(job_id)

    def get_events(self, job_id: str) -> list[dict]:
        return self.jobs.events(job_id)
