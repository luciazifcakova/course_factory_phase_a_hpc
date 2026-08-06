from __future__ import annotations

from pathlib import Path

from .agent import Agent
from .agent_result import AgentResult
from .execution_models import (
    ExecutionReport,
    ExecutionRequest,
    ExecutionRuntime,
)
from .job_context import JobContext
from .r_code_models import RScriptArtifact
from .r_executor import RExecutor
from .workspace_manager import WorkspaceManager


class ExecutionAgent(Agent):
    name = "r_executor"
    version = "1.0.0"
    capabilities = frozenset({"r_execution"})

    def __init__(
        self,
        *,
        executor: RExecutor | None = None,
        workspace: str | Path = "workspace/execution",
        runtime: ExecutionRuntime = ExecutionRuntime.APPTAINER,
        apptainer_image: str | Path | None = None,
        timeout_seconds: int = 900,
    ) -> None:
        self.executor = executor or RExecutor()
        self.workspace = Path(workspace)
        self.runtime = runtime
        self.apptainer_image = (
            str(apptainer_image) if apptainer_image is not None else None
        )
        self.timeout_seconds = timeout_seconds

    def run(self, context: JobContext) -> AgentResult:
        scripts_raw = context.state.get("approved_r_scripts")
        if not isinstance(scripts_raw, list):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("approved_r_scripts is missing",),
            )

        manager = WorkspaceManager(self.workspace)
        manager.initialize()
        results = []
        successful: list[str] = []
        failed: list[str] = []

        try:
            for raw in scripts_raw:
                script = RScriptArtifact.model_validate(raw)
                source = Path(script.relative_path).resolve()
                task_workspace = manager.task_directory(
                    job_id=context.job_id,
                    task_id=script.task_id,
                )
                target = task_workspace / "script.R"
                target.write_text(
                    script.code.rstrip() + "\n",
                    encoding="utf-8",
                )

                request = ExecutionRequest(
                    task_id=script.task_id,
                    lesson_id=script.lesson_id,
                    script_path=str(target),
                    workspace=str(task_workspace),
                    runtime=self.runtime,
                    apptainer_image=self.apptainer_image,
                    expected_outputs=script.expected_outputs,
                    timeout_seconds=self.timeout_seconds,
                )
                result = self.executor.execute(request)
                results.append(result)
                if result.succeeded:
                    successful.append(result.task_id)
                else:
                    failed.append(result.task_id)

            report = ExecutionReport(
                results=tuple(results),
                successful_tasks=tuple(successful),
                failed_tasks=tuple(failed),
                artifact_count=sum(
                    len(result.collected_artifacts) for result in results
                ),
            )
        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "execution_report": report.model_dump(mode="json"),
                "execution_artifacts": [
                    artifact.model_dump(mode="json")
                    for result in report.results
                    for artifact in result.collected_artifacts
                ],
            },
            metrics={
                "executed_r_scripts": len(report.results),
                "successful_r_scripts": len(report.successful_tasks),
                "failed_r_scripts": len(report.failed_tasks),
                "execution_artifacts": report.artifact_count,
            },
        )
