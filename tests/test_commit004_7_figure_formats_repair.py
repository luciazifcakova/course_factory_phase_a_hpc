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
    def __init__(self, response):
        self.response = response

    def generate_json(self, **kwargs):
        return self.response


class FailsThenSucceedsRouter:
    def __init__(self):
        self.calls = 0

    def execute(self, task):
        self.calls += 1
        output = Path(task.working_directory) / "output"

        if self.calls == 1:
            return RuntimeResult(
                task_id=task.task_id,
                runtime=task.runtime,
                return_code=1,
                stdout="",
                stderr="simulated failure",
                submitted=True,
                completed=True,
            )

        (output / "figures").mkdir(
            parents=True,
            exist_ok=True,
        )
        (output / "figures" / "plot.png").write_bytes(
            b"png"
        )
        (output / "figures" / "plot.pdf").write_bytes(
            b"pdf"
        )

        return RuntimeResult(
            task_id=task.task_id,
            runtime=task.runtime,
            return_code=0,
            stdout="ok",
            stderr="",
            submitted=True,
            completed=True,
        )


def cfg(tmp_path):
    image = tmp_path / "course-r.sif"
    image.write_bytes(b"image")

    return HPCSettings(
        workspace=tmp_path / "workspace",
        apptainer_image=image,
        allowed_r_packages=("base", "ggplot2"),
        slurm_partition="cpu",
        slurm_cpus=2,
        slurm_memory_gb=8,
        slurm_time_minutes=60,
        slurm_poll_seconds=1,
        slurm_wait_seconds=60,
        local_timeout_seconds=60,
        r_execution_repair_attempts=2,
    )


def test_svg_may_be_removed_by_repair(tmp_path):
    settings = cfg(tmp_path)
    workspace = WorkspaceManager(
        settings.workspace
    )
    workspace.initialize()

    source = tmp_path / "LES-005.R"
    source.write_text(
        'library(ggplot2)\n'
        'dir.create("figures", showWarnings=FALSE)\n'
        'p <- ggplot(mtcars, aes(wt, mpg)) + geom_point()\n'
        'ggsave("figures/plot.png", p)\n'
        'ggsave("figures/plot.pdf", p)\n'
        'ggsave("figures/plot.svg", p)\n',
        encoding="utf-8",
    )

    script = RScriptArtifact(
        task_id="LES-005.r_code",
        lesson_id="LES-005",
        relative_path=str(source),
        code=source.read_text(),
        required_packages=("ggplot2",),
        expected_outputs=(
            "figures/plot.png",
            "figures/plot.pdf",
            "figures/plot.svg",
        ),
        knowledge_ids=(),
    )

    report = CourseExecutionService(
        settings=settings,
        workspace=workspace,
        router=FailsThenSucceedsRouter(),
        backend=RepairBackend({
            "code": (
                'library(ggplot2)\n'
                'dir.create("figures", showWarnings=FALSE)\n'
                'p <- ggplot(mtcars, aes(wt, mpg)) + geom_point()\n'
                'ggsave("figures/plot.png", p)\n'
                'ggsave("figures/plot.pdf", p)\n'
            ),
            "expected_outputs": [
                "figures/plot.png",
                "figures/plot.pdf",
            ],
            "knowledge_ids": [],
        }),
    ).execute(
        job_id="job-svg",
        scripts=(script,),
        request=CreateCourseRequest(
            prompt="Create course",
            executor=CourseExecutor.LOCAL,
        ),
    )

    assert report.succeeded
    assert report.results[0].repair_count == 1


def test_empty_repair_output_list_preserves_png_contract(
    tmp_path,
):
    settings = cfg(tmp_path)
    workspace = WorkspaceManager(
        settings.workspace
    )
    workspace.initialize()

    source = tmp_path / "LES-003.R"
    source.write_text(
        'library(ggplot2)\n'
        'dir.create("figures", showWarnings=FALSE)\n'
        'p <- ggplot(mtcars, aes(wt, mpg)) + geom_point()\n'
        'ggsave("figures/plot.png", p)\n',
        encoding="utf-8",
    )

    script = RScriptArtifact(
        task_id="LES-003.r_code",
        lesson_id="LES-003",
        relative_path=str(source),
        code=source.read_text(),
        required_packages=("ggplot2",),
        expected_outputs=("figures/plot.png",),
        knowledge_ids=(),
    )

    report = CourseExecutionService(
        settings=settings,
        workspace=workspace,
        router=FailsThenSucceedsRouter(),
        backend=RepairBackend({
            "code": (
                'library(ggplot2)\n'
                'dir.create("figures", showWarnings=FALSE)\n'
                'p <- ggplot(mtcars, aes(wt, mpg)) + '
                'geom_point() + scale_x_log10()\n'
                'ggsave("figures/plot.png", p)\n'
            ),
            "expected_outputs": [],
            "knowledge_ids": [],
        }),
    ).execute(
        job_id="job-log",
        scripts=(script,),
        request=CreateCourseRequest(
            prompt="Create course",
            executor=CourseExecutor.LOCAL,
        ),
    )

    assert report.succeeded
    assert report.results[0].repair_count == 1
