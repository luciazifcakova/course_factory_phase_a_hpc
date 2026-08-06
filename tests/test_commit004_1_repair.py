from pathlib import Path

from course_factory import (
    CourseExecutionService,
    CourseExecutor,
    CreateCourseRequest,
    HPCSettings,
    RScriptArtifact,
    RuntimeResult,
    WorkspaceManager,
)


class RepairBackend:
    def __init__(self):
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        return {
            "code": (
                'dir.create("figures", recursive=TRUE, '
                'showWarnings=FALSE)\n'
                'png("figures/LES-001.png")\n'
                'plot(1)\n'
                'dev.off()\n'
            ),
            "expected_outputs": [
                "figures/LES-001.png"
            ],
            "knowledge_ids": [],
        }


class FailsThenSucceedsRouter:
    def __init__(self):
        self.calls = 0

    def execute(self, task):
        self.calls += 1
        output = (
            Path(task.working_directory)
            / "output"
        )
        if self.calls == 1:
            (output / "plots").mkdir(
                parents=True,
                exist_ok=True,
            )
            (
                output / "plots" / "LES-001.png"
            ).write_bytes(b"wrong")
            return RuntimeResult(
                task_id=task.task_id,
                runtime=task.runtime,
                return_code=0,
                stdout="",
                stderr="",
                submitted=True,
                completed=True,
            )

        (output / "figures").mkdir(
            parents=True,
            exist_ok=True,
        )
        (
            output / "figures" / "LES-001.png"
        ).write_bytes(b"correct")
        return RuntimeResult(
            task_id=task.task_id,
            runtime=task.runtime,
            return_code=0,
            stdout="ok",
            stderr="",
            submitted=True,
            completed=True,
        )


def configuration(tmp_path):
    image = tmp_path / "course-r.sif"
    image.write_bytes(b"image")
    return HPCSettings(
        workspace=tmp_path / "workspace",
        apptainer_image=image,
        allowed_r_packages=(
            "base",
            "ggplot2",
        ),
        slurm_partition="cpu",
        slurm_cpus=2,
        slurm_memory_gb=8,
        slurm_time_minutes=60,
        slurm_poll_seconds=1,
        slurm_wait_seconds=60,
        local_timeout_seconds=60,
        r_execution_repair_attempts=2,
    )


def script(tmp_path):
    source = tmp_path / "LES-001.R"
    source.write_text(
        'dir.create("plots", showWarnings=FALSE)\n'
        'png("plots/LES-001.png")\n'
        'plot(1)\n'
        'dev.off()\n',
        encoding="utf-8",
    )
    return RScriptArtifact(
        task_id="LES-001.r_code",
        lesson_id="LES-001",
        relative_path=str(source),
        code=source.read_text(encoding="utf-8"),
        required_packages=(),
        expected_outputs=(
            "figures/LES-001.png",
        ),
        knowledge_ids=(),
    )


def test_failed_output_path_is_repaired_and_reexecuted(
    tmp_path,
):
    cfg = configuration(tmp_path)
    workspace = WorkspaceManager(cfg.workspace)
    workspace.initialize()
    backend = RepairBackend()
    router = FailsThenSucceedsRouter()

    report = CourseExecutionService(
        settings=cfg,
        workspace=workspace,
        router=router,
        backend=backend,
    ).execute(
        job_id="job1",
        scripts=(script(tmp_path),),
        request=CreateCourseRequest(
            prompt="Create a ggplot2 course",
            executor=CourseExecutor.LOCAL,
        ),
    )

    assert report.succeeded
    assert report.repair_attempt_count == 1
    assert report.repaired_task_ids == (
        "LES-001.r_code",
    )
    assert backend.calls == 1
    assert router.calls == 2

    result = report.results[0]
    assert result.repair_count == 1
    assert len(result.attempts) == 2
    assert (
        result.expected_outputs_found
        == ("figures/LES-001.png",)
    )
    assert Path(result.final_script_path).is_file()
    assert (
        "figures/LES-001.png"
        in Path(
            result.final_script_path
        ).read_text(encoding="utf-8")
    )


def test_repair_request_and_response_are_persisted(
    tmp_path,
):
    cfg = configuration(tmp_path)
    workspace = WorkspaceManager(cfg.workspace)
    workspace.initialize()

    report = CourseExecutionService(
        settings=cfg,
        workspace=workspace,
        router=FailsThenSucceedsRouter(),
        backend=RepairBackend(),
    ).execute(
        job_id="job2",
        scripts=(script(tmp_path),),
        request=CreateCourseRequest(
            prompt="Create a ggplot2 course",
            executor=CourseExecutor.LOCAL,
        ),
    )

    first = report.results[0].attempts[0]
    assert first.repair_request_path is not None
    assert first.repair_response_path is not None
    assert Path(first.repair_request_path).is_file()
    assert Path(first.repair_response_path).is_file()


def test_no_backend_keeps_original_failure(
    tmp_path,
):
    class AlwaysMissingRouter:
        def execute(self, task):
            return RuntimeResult(
                task_id=task.task_id,
                runtime=task.runtime,
                return_code=0,
                stdout="",
                stderr="",
                submitted=True,
                completed=True,
            )

    cfg = configuration(tmp_path)
    workspace = WorkspaceManager(cfg.workspace)
    workspace.initialize()

    report = CourseExecutionService(
        settings=cfg,
        workspace=workspace,
        router=AlwaysMissingRouter(),
        backend=None,
    ).execute(
        job_id="job3",
        scripts=(script(tmp_path),),
        request=CreateCourseRequest(
            prompt="Create a ggplot2 course",
            executor=CourseExecutor.LOCAL,
        ),
    )

    assert not report.succeeded
    assert report.repair_attempt_count == 0
    assert (
        "No LLM backend"
        in report.results[0]
        .attempts[0]
        .repair_validation_errors[0]
    )
