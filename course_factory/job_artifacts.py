from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .course_execution_models import (
    CourseExecutionReport,
    ExecutedOutput,
)
from .course_outline import CourseOutline
from .lesson_content_models import LessonContentSet
from .r_code_models import RScriptArtifact
from .workflow_plan import TaskType, WorkflowPlan


class ManifestFile(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    relative_path: str
    absolute_path: str
    content_type: str
    size_bytes: int = Field(default=0, ge=0)
    sha256: str | None = None


class LessonArtifactManifest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    lesson_id: str
    title: str
    markdown: ManifestFile | None = None
    script: ManifestFile | None = None
    figures: tuple[ManifestFile, ...] = ()
    other_outputs: tuple[ManifestFile, ...] = ()
    execution_status: str = "not_executed"
    repair_count: int = Field(default=0, ge=0)


class ArtifactManifest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    job_id: str
    generated_at: str
    course_title: str
    lessons: tuple[LessonArtifactManifest, ...]
    summary: dict[str, int | float | str | bool]


def _content_type(path: Path) -> str:
    return {
        ".md": "text/markdown",
        ".r": "text/x-r-source",
        ".png": "image/png",
        ".pdf": "application/pdf",
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".json": "application/json",
        ".html": "text/html",
        ".txt": "text/plain",
    }.get(
        path.suffix.lower(),
        "application/octet-stream",
    )


def _relative(
    path: str | Path,
    job_directory: Path,
) -> str:
    value = Path(path)
    try:
        return value.resolve().relative_to(
            job_directory.resolve()
        ).as_posix()
    except (ValueError, OSError):
        return value.as_posix()


def _manifest_file(
    *,
    path: str | Path,
    job_directory: Path,
    sha256: str | None = None,
) -> ManifestFile:
    value = Path(path)
    size = (
        value.stat().st_size
        if value.is_file()
        else 0
    )
    return ManifestFile(
        relative_path=_relative(
            value,
            job_directory,
        ),
        absolute_path=str(value),
        content_type=_content_type(value),
        size_bytes=size,
        sha256=sha256,
    )


def _execution_file(
    output: ExecutedOutput,
    *,
    job_directory: Path,
) -> ManifestFile:
    path = Path(output.absolute_path)
    return ManifestFile(
        relative_path=_relative(
            path,
            job_directory,
        ),
        absolute_path=output.absolute_path,
        content_type=_content_type(path),
        size_bytes=output.size_bytes,
        sha256=output.sha256,
    )


def build_observability_metrics(
    *,
    workflow_plan: WorkflowPlan,
    approved_scripts: tuple[
        RScriptArtifact,
        ...,
    ],
    execution_report: CourseExecutionReport | None,
) -> dict[str, int | float | str | bool]:
    planned_r = sum(
        task.task_type is TaskType.R_SCRIPT
        for task in workflow_plan.tasks
    )
    planned_figures = sum(
        task.task_type is TaskType.FIGURE
        for task in workflow_plan.tasks
    )
    planned_slides = sum(
        task.task_type is TaskType.SLIDE_CONTENT
        for task in workflow_plan.tasks
    )
    planned_tables = sum(
        task.task_type is TaskType.TABLE
        for task in workflow_plan.tasks
    )

    outputs = (
        tuple(
            output
            for result in execution_report.results
            for output in result.outputs
        )
        if execution_report is not None
        else ()
    )

    figure_outputs = tuple(
        output
        for output in outputs
        if Path(output.relative_path).suffix.lower()
        in {".png", ".pdf"}
        and (
            Path(output.relative_path).parts
            and Path(output.relative_path).parts[0]
            == "figures"
        )
    )
    png_outputs = tuple(
        output
        for output in figure_outputs
        if Path(
            output.relative_path
        ).suffix.lower() == ".png"
    )
    pdf_outputs = tuple(
        output
        for output in figure_outputs
        if Path(
            output.relative_path
        ).suffix.lower() == ".pdf"
    )
    table_outputs = tuple(
        output
        for output in outputs
        if Path(output.relative_path).suffix.lower()
        in {".csv", ".tsv"}
    )

    return {
        "planned_workflow_task_count": len(
            workflow_plan.tasks
        ),
        "planned_r_script_task_count": planned_r,
        "planned_figure_task_count": planned_figures,
        "planned_slide_task_count": planned_slides,
        "planned_table_task_count": planned_tables,
        "generated_r_script_count": len(
            approved_scripts
        ),
        "generated_output_count": len(outputs),
        "generated_figure_count": len(
            figure_outputs
        ),
        "generated_png_count": len(
            png_outputs
        ),
        "generated_pdf_count": len(
            pdf_outputs
        ),
        "generated_table_count": len(
            table_outputs
        ),
        "executed_r_script_count": (
            len(execution_report.results)
            if execution_report is not None
            else 0
        ),
        "successful_r_script_count": (
            len(
                execution_report
                .successful_task_ids
            )
            if execution_report is not None
            else 0
        ),
        "failed_r_script_count": (
            len(execution_report.failed_task_ids)
            if execution_report is not None
            else 0
        ),
        "execution_repair_attempt_count": (
            execution_report.repair_attempt_count
            if execution_report is not None
            else 0
        ),
        "repaired_r_script_count": (
            len(execution_report.repaired_task_ids)
            if execution_report is not None
            else 0
        ),
        "execution_seconds_total": round(
            sum(
                result.runtime_result.duration_seconds
                for result in execution_report.results
            ),
            3,
        )
        if execution_report is not None
        else 0.0,
    }


def build_artifact_manifest(
    *,
    job_id: str,
    job_directory: Path,
    outline: CourseOutline,
    lesson_content: LessonContentSet,
    lesson_paths: tuple[Path, ...],
    approved_scripts: tuple[
        RScriptArtifact,
        ...,
    ],
    execution_report: CourseExecutionReport | None,
    summary_metrics: dict[
        str,
        int | float | str | bool,
    ],
) -> ArtifactManifest:
    markdown_paths = lesson_paths[1:]
    markdown_by_lesson = {
        lesson.lesson_id: path
        for lesson, path in zip(
            lesson_content.lessons,
            markdown_paths,
            strict=False,
        )
    }
    scripts_by_lesson = {
        script.lesson_id: script
        for script in approved_scripts
    }
    execution_by_lesson = (
        {
            result.lesson_id: result
            for result in execution_report.results
        }
        if execution_report is not None
        else {}
    )

    lesson_entries = []
    for module in outline.modules:
        for lesson in module.lessons:
            markdown = markdown_by_lesson.get(
                lesson.lesson_id
            )
            script = scripts_by_lesson.get(
                lesson.lesson_id
            )
            execution = execution_by_lesson.get(
                lesson.lesson_id
            )

            figures: list[ManifestFile] = []
            other_outputs: list[
                ManifestFile
            ] = []

            if execution is not None:
                for output in execution.outputs:
                    manifest_file = _execution_file(
                        output,
                        job_directory=job_directory,
                    )
                    path = Path(
                        output.relative_path
                    )
                    if (
                        path.parts
                        and path.parts[0] == "figures"
                        and path.suffix.lower()
                        in {".png", ".pdf"}
                    ):
                        figures.append(
                            manifest_file
                        )
                    else:
                        other_outputs.append(
                            manifest_file
                        )

            lesson_entries.append(
                LessonArtifactManifest(
                    lesson_id=lesson.lesson_id,
                    title=lesson.title,
                    markdown=(
                        _manifest_file(
                            path=markdown,
                            job_directory=(
                                job_directory
                            ),
                        )
                        if markdown is not None
                        else None
                    ),
                    script=(
                        _manifest_file(
                            path=script.relative_path,
                            job_directory=(
                                job_directory
                            ),
                        )
                        if script is not None
                        else None
                    ),
                    figures=tuple(figures),
                    other_outputs=tuple(
                        other_outputs
                    ),
                    execution_status=(
                        "completed"
                        if (
                            execution is not None
                            and execution.succeeded
                        )
                        else (
                            "failed"
                            if execution is not None
                            else "not_executed"
                        )
                    ),
                    repair_count=(
                        execution.repair_count
                        if execution is not None
                        else 0
                    ),
                )
            )

    return ArtifactManifest(
        job_id=job_id,
        generated_at=(
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        course_title=outline.title,
        lessons=tuple(lesson_entries),
        summary=dict(summary_metrics),
    )


def render_job_index(
    manifest: ArtifactManifest,
) -> str:
    rows = []
    for lesson in manifest.lessons:
        links = []

        if lesson.markdown is not None:
            links.append(
                '<a href="{}">lesson markdown</a>'.format(
                    escape(
                        lesson.markdown.relative_path,
                        quote=True,
                    )
                )
            )
        if lesson.script is not None:
            links.append(
                '<a href="{}">R script</a>'.format(
                    escape(
                        lesson.script.relative_path,
                        quote=True,
                    )
                )
            )

        figure_html = []
        for figure in lesson.figures:
            relative = escape(
                figure.relative_path,
                quote=True,
            )
            if (
                Path(
                    figure.relative_path
                ).suffix.lower()
                == ".png"
            ):
                figure_html.append(
                    (
                        '<a href="{0}">'
                        '<img src="{0}" '
                        'alt="{1}" loading="lazy">'
                        "</a>"
                    ).format(
                        relative,
                        escape(
                            Path(
                                figure.relative_path
                            ).name
                        )
                    )
                )
            else:
                figure_html.append(
                    '<a href="{}">{}</a>'.format(
                        relative,
                        escape(
                            Path(
                                figure.relative_path
                            ).name
                        ),
                    )
                )

        rows.append(
            """
            <section class="lesson">
              <h2>{lesson_id}: {title}</h2>
              <p><strong>Status:</strong> {status}
                 &nbsp; <strong>Repairs:</strong> {repairs}</p>
              <p>{links}</p>
              <div class="figures">{figures}</div>
            </section>
            """.format(
                lesson_id=escape(
                    lesson.lesson_id
                ),
                title=escape(lesson.title),
                status=escape(
                    lesson.execution_status
                ),
                repairs=lesson.repair_count,
                links=" · ".join(links)
                if links
                else "No lesson files",
                figures="\n".join(
                    figure_html
                )
                if figure_html
                else (
                    '<span class="muted">'
                    "No figures</span>"
                ),
            )
        )

    summary = " · ".join(
        "{}: {}".format(
            escape(str(key)),
            escape(str(value)),
        )
        for key, value in manifest.summary.items()
        if key
        in {
            "generated_r_script_count",
            "generated_figure_count",
            "execution_repair_attempt_count",
            "successful_r_script_count",
            "failed_r_script_count",
        }
    )

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Course Factory job</title>
  <style>
    body {{
      font-family: system-ui, sans-serif;
      max-width: 1100px;
      margin: 2rem auto;
      padding: 0 1rem;
      line-height: 1.45;
    }}
    .meta {{ color: #555; }}
    .lesson {{
      border-top: 1px solid #ddd;
      padding: 1rem 0 1.5rem;
    }}
    .figures {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: flex-start;
    }}
    .figures img {{
      width: 320px;
      max-width: 100%;
      border: 1px solid #ddd;
    }}
    .muted {{ color: #777; }}
    code {{
      background: #f5f5f5;
      padding: .1rem .3rem;
    }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">Job <code>{job_id}</code></p>
  <p class="meta">{summary}</p>
  {lessons}
</body>
</html>
""".format(
        title=escape(
            manifest.course_title
        ),
        job_id=escape(manifest.job_id),
        summary=summary,
        lessons="\n".join(rows),
    )


def render_job_summary(
    manifest: ArtifactManifest,
) -> str:
    metrics = manifest.summary
    lines = [
        "=" * 58,
        "Course generation finished",
        "=" * 58,
        "",
        f"Course            : {manifest.course_title}",
        f"Job               : {manifest.job_id}",
        f"Lessons           : {len(manifest.lessons)}",
        (
            "R scripts         : "
            f"{metrics.get('generated_r_script_count', 0)}"
        ),
        (
            "Figures           : "
            f"{metrics.get('generated_figure_count', 0)}"
        ),
        (
            "PNG figures       : "
            f"{metrics.get('generated_png_count', 0)}"
        ),
        (
            "PDF figures       : "
            f"{metrics.get('generated_pdf_count', 0)}"
        ),
        (
            "Repairs           : "
            f"{metrics.get('execution_repair_attempt_count', 0)}"
        ),
        (
            "Execution failures: "
            f"{metrics.get('failed_r_script_count', 0)}"
        ),
        "",
        "=" * 58,
    ]
    return "\n".join(lines) + "\n"
