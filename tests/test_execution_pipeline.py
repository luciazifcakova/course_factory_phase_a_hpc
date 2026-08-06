from pathlib import Path

from course_factory import (
    AgentStatus,
    ArtifactCollector,
    ExecutionAgent,
    ExecutionRequest,
    ExecutionRuntime,
    JobContext,
    LocalRBackend,
    RExecutor,
)


class FakeBackend:
    def validate(self, request):
        return None

    def build_command(self, request):
        return (
            "python",
            "-c",
            (
                "from pathlib import Path; "
                "Path('figures').mkdir(exist_ok=True); "
                "Path('figures/out.png').write_bytes(b'PNG'); "
                "print('done')"
            ),
        )


def test_artifact_collector_detects_new_files(tmp_path):
    before = ArtifactCollector.snapshot(tmp_path)
    figures = tmp_path / "figures"
    figures.mkdir()
    (figures / "plot.png").write_bytes(b"PNG")

    artifacts = ArtifactCollector().collect(
        workspace=tmp_path,
        task_id="lesson.plot",
        before=before,
    )

    assert len(artifacts) == 1
    assert artifacts[0].kind == "figure"
    assert artifacts[0].relative_path == "figures/plot.png"


def test_executor_collects_outputs_with_fake_backend(tmp_path):
    script = tmp_path / "lesson.R"
    script.write_text("# not executed by fake backend\n", encoding="utf-8")

    executor = RExecutor(
        local_backend=FakeBackend(),
        apptainer_backend=FakeBackend(),
    )
    result = executor.execute(
        ExecutionRequest(
            task_id="lesson.r",
            lesson_id="lesson",
            script_path=str(script),
            workspace=str(tmp_path),
            runtime=ExecutionRuntime.LOCAL,
            expected_outputs=("figures/out.png",),
        )
    )

    assert result.succeeded is True
    assert result.expected_outputs_found == ("figures/out.png",)
    assert len(result.collected_artifacts) == 1
    assert result.collected_artifacts[0].kind == "figure"


def test_execution_agent_returns_report(tmp_path):
    generated = tmp_path / "generated.R"
    generated.write_text("# placeholder\n", encoding="utf-8")

    executor = RExecutor(
        local_backend=FakeBackend(),
        apptainer_backend=FakeBackend(),
    )
    agent = ExecutionAgent(
        executor=executor,
        workspace=tmp_path / "execution",
        runtime=ExecutionRuntime.LOCAL,
    )
    context = JobContext.create(user_request="Execute R code").model_copy(
        update={
            "state": {
                "approved_r_scripts": [
                    {
                        "task_id": "lesson.r",
                        "lesson_id": "lesson",
                        "relative_path": str(generated),
                        "code": "# placeholder",
                        "required_packages": [],
                        "expected_outputs": ["figures/out.png"],
                        "knowledge_ids": [],
                    }
                ]
            }
        }
    )

    result = agent.run(context)

    assert result.status is AgentStatus.SUCCESS
    assert result.metrics["successful_r_scripts"] == 1
    assert result.metrics["execution_artifacts"] == 1
    assert (
        result.outputs["execution_artifacts"][0]["relative_path"]
        == "figures/out.png"
    )
