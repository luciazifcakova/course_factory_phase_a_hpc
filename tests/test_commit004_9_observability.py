from pathlib import Path

from course_factory import (
    ArtifactManifest,
    CourseExecutionReport,
    CourseScriptExecution,
    ExecutedOutput,
    RScriptArtifact,
    RuntimeKind,
    RuntimeResult,
    build_artifact_manifest,
    build_observability_metrics,
    render_job_index,
    render_job_summary,
)
from course_factory.course_outline import (
    CourseModule,
    CourseOutline,
    Lesson,
)
from course_factory.lesson_content_models import (
    LessonContent,
    LessonContentSet,
    LessonSection,
)
from course_factory.workflow_plan import (
    TaskType,
    WorkflowPlan,
    WorkflowTask,
)


def runtime_result(task_id: str):
    return RuntimeResult(
        task_id=task_id,
        runtime=RuntimeKind.LOCAL,
        return_code=0,
        stdout="",
        stderr="",
        submitted=True,
        completed=True,
        duration_seconds=1.25,
    )


def test_observability_metrics_distinguish_plans_from_files(
    tmp_path,
):
    plan = WorkflowPlan(
        course_title="Course",
        tasks=(
            WorkflowTask(
                task_id="LES-001.r_code",
                task_type=TaskType.R_SCRIPT,
                lesson_id="LES-001",
                description="R code",
            ),
            WorkflowTask(
                task_id="LES-001.slides",
                task_type=TaskType.SLIDE_CONTENT,
                lesson_id="LES-001",
                description="Slides",
            ),
        ),
    )

    png = tmp_path / "plot.png"
    pdf = tmp_path / "plot.pdf"
    png.write_bytes(b"png")
    pdf.write_bytes(b"pdf")

    result = CourseScriptExecution(
        task_id="LES-001.r_code",
        lesson_id="LES-001",
        runtime_result=runtime_result(
            "LES-001.r_code"
        ),
        expected_outputs_found=(
            "figures/plot.png",
        ),
        outputs=(
            ExecutedOutput(
                relative_path="figures/plot.png",
                absolute_path=str(png),
                size_bytes=3,
                sha256="a" * 64,
            ),
            ExecutedOutput(
                relative_path="figures/plot.pdf",
                absolute_path=str(pdf),
                size_bytes=3,
                sha256="b" * 64,
            ),
        ),
        final_script_path="/tmp/script.R",
    )
    execution = CourseExecutionReport(
        executor=RuntimeKind.LOCAL,
        results=(result,),
        successful_task_ids=(
            "LES-001.r_code",
        ),
        failed_task_ids=(),
        output_count=2,
    )

    script = RScriptArtifact(
        task_id="LES-001.r_code",
        lesson_id="LES-001",
        relative_path="/tmp/LES-001.R",
        code="# code",
    )

    metrics = build_observability_metrics(
        workflow_plan=plan,
        approved_scripts=(script,),
        execution_report=execution,
    )

    assert metrics[
        "planned_figure_task_count"
    ] == 0
    assert metrics[
        "planned_slide_task_count"
    ] == 1
    assert metrics[
        "generated_figure_count"
    ] == 2
    assert metrics[
        "generated_png_count"
    ] == 1
    assert metrics[
        "generated_pdf_count"
    ] == 1
    assert metrics[
        "execution_seconds_total"
    ] == 1.25


def test_manifest_groups_artifacts_by_lesson(
    tmp_path,
):
    job = tmp_path / "job"
    lessons_dir = job / "lessons"
    scripts_dir = job / "scripts"
    output_dir = (
        job
        / "tasks"
        / "LES-001.r_code"
        / "output"
        / "figures"
    )
    lessons_dir.mkdir(parents=True)
    scripts_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    md = lessons_dir / "01_intro.md"
    script_path = scripts_dir / "LES-001.R"
    figure = output_dir / "plot.png"
    md.write_text("# Intro\n", encoding="utf-8")
    script_path.write_text("# R\n", encoding="utf-8")
    figure.write_bytes(b"png")

    outline = CourseOutline(
        title="Test Course",
        audience="Scientists",
        language="English",
        modules=(
            CourseModule(
                module_id="mod_001",
                title="Module",
                lessons=(
                    Lesson(
                        lesson_id="LES-001",
                        title="Intro",
                        duration_minutes=30,
                    ),
                ),
            ),
        ),
        learning_objectives=("Learn",),
        total_duration_minutes=30,
    )
    content = LessonContentSet(
        course_title="Test Course",
        lessons=(
            LessonContent(
                lesson_id="LES-001",
                title="Intro",
                summary="This lesson summary contains enough explanatory detail.",
                sections=(
                    LessonSection(
                        heading="Section",
                        content="This section contains enough explanatory content.",
                    ),
                ),
                key_takeaways=("Takeaway",),
            ),
        ),
    )
    script = RScriptArtifact(
        task_id="LES-001.r_code",
        lesson_id="LES-001",
        relative_path=str(script_path),
        code="# R",
    )
    execution = CourseExecutionReport(
        executor=RuntimeKind.LOCAL,
        results=(
            CourseScriptExecution(
                task_id="LES-001.r_code",
                lesson_id="LES-001",
                runtime_result=runtime_result(
                    "LES-001.r_code"
                ),
                expected_outputs_found=(
                    "figures/plot.png",
                ),
                outputs=(
                    ExecutedOutput(
                        relative_path=(
                            "figures/plot.png"
                        ),
                        absolute_path=str(figure),
                        size_bytes=3,
                        sha256="a" * 64,
                    ),
                ),
                final_script_path=str(
                    script_path
                ),
                repair_count=1,
            ),
        ),
        successful_task_ids=(
            "LES-001.r_code",
        ),
        failed_task_ids=(),
        output_count=1,
        repair_attempt_count=1,
        repaired_task_ids=(
            "LES-001.r_code",
        ),
    )

    manifest = build_artifact_manifest(
        job_id="job1",
        job_directory=job,
        outline=outline,
        lesson_content=content,
        lesson_paths=(
            lessons_dir / "README.md",
            md,
        ),
        approved_scripts=(script,),
        execution_report=execution,
        summary_metrics={
            "generated_figure_count": 1,
            "generated_r_script_count": 1,
        },
    )

    assert isinstance(
        manifest,
        ArtifactManifest,
    )
    lesson = manifest.lessons[0]
    assert lesson.lesson_id == "LES-001"
    assert lesson.markdown.relative_path == (
        "lessons/01_intro.md"
    )
    assert lesson.script.relative_path == (
        "scripts/LES-001.R"
    )
    assert lesson.figures[0].relative_path.endswith(
        "figures/plot.png"
    )
    assert lesson.execution_status == "completed"
    assert lesson.repair_count == 1

    html = render_job_index(manifest)
    assert "LES-001" in html
    assert "plot.png" in html

    summary = render_job_summary(manifest)
    assert "Course generation finished" in summary
    assert "Figures" in summary
