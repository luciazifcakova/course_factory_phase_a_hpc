from pathlib import Path

from course_factory import (
    CourseExecutionService,
    CourseExecutor,
    CreateCourseRequest,
    HPCSettings,
    RScriptArtifact,
    RuntimeKind,
    RuntimeResult,
    WorkspaceManager,
)


class FakeRouter:
    def execute(self, task):
        output_dir = (
            Path(task.working_directory)
            / "output"
        )
        (
            output_dir / "figures"
        ).mkdir(
            parents=True,
            exist_ok=True,
        )
        (
            output_dir
            / "figures"
            / "LES-001.png"
        ).write_bytes(b"PNG")

        return RuntimeResult(
            task_id=task.task_id,
            runtime=task.runtime,
            return_code=0,
            stdout="ok",
            stderr="",
            submitted=True,
            completed=True,
        )


def settings(tmp_path):
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
    )


def script(tmp_path):
    source = tmp_path / "LES-001.R"
    source.write_text(
        'dir.create("figures", showWarnings=FALSE)\n'
        'png("figures/LES-001.png")\n'
        'plot(1)\n'
        'dev.off()\n',
        encoding="utf-8",
    )
    return RScriptArtifact(
        task_id="LES-001.r_code",
        lesson_id="LES-001",
        relative_path=str(source),
        code=source.read_text(encoding="utf-8"),
        required_packages=("ggplot2",),
        expected_outputs=(
            "figures/LES-001.png",
        ),
        knowledge_ids=(),
    )


def test_execution_service_collects_expected_outputs(
    tmp_path,
):
    configuration = settings(tmp_path)
    workspace = WorkspaceManager(
        configuration.workspace
    )
    workspace.initialize()

    report = CourseExecutionService(
        settings=configuration,
        workspace=workspace,
        router=FakeRouter(),
    ).execute(
        job_id="job1",
        scripts=(script(tmp_path),),
        request=CreateCourseRequest(
            prompt="Create a ggplot2 course",
            executor=CourseExecutor.LOCAL,
        ),
    )

    assert report.succeeded
    assert report.successful_task_ids == (
        "LES-001.r_code",
    )
    assert report.output_count == 1
    assert (
        report.results[0]
        .expected_outputs_found
        == ("figures/LES-001.png",)
    )


def test_missing_output_marks_execution_failed(
    tmp_path,
):
    class EmptyRouter:
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

    configuration = settings(tmp_path)
    workspace = WorkspaceManager(
        configuration.workspace
    )
    workspace.initialize()

    report = CourseExecutionService(
        settings=configuration,
        workspace=workspace,
        router=EmptyRouter(),
    ).execute(
        job_id="job2",
        scripts=(script(tmp_path),),
        request=CreateCourseRequest(
            prompt="Create a ggplot2 course",
            executor=CourseExecutor.LOCAL,
        ),
    )

    assert not report.succeeded
    assert report.failed_task_ids == (
        "LES-001.r_code",
    )
    assert (
        report.results[0]
        .expected_outputs_missing
        == ("figures/LES-001.png",)
    )


def test_slurm_request_routes_to_slurm(
    tmp_path,
):
    seen = {}

    class CapturingRouter(FakeRouter):
        def execute(self, task):
            seen["runtime"] = task.runtime
            return super().execute(task)

    configuration = settings(tmp_path)
    workspace = WorkspaceManager(
        configuration.workspace
    )
    workspace.initialize()

    CourseExecutionService(
        settings=configuration,
        workspace=workspace,
        router=CapturingRouter(),
    ).execute(
        job_id="job3",
        scripts=(script(tmp_path),),
        request=CreateCourseRequest(
            prompt="Create a ggplot2 course",
            executor=CourseExecutor.SLURM,
        ),
    )

    assert seen["runtime"] is RuntimeKind.SLURM
