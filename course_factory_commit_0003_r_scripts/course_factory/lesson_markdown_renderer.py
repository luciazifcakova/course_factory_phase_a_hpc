from __future__ import annotations

import re
from pathlib import Path

from .course_outline import CourseOutline
from .lesson_content_models import LessonContent, LessonContentSet


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "lesson"


class LessonMarkdownRenderer:
    def render_lesson(
        self,
        *,
        lesson: LessonContent,
        objectives: tuple[str, ...],
        duration_minutes: int,
    ) -> str:
        lines = [
            f"# {lesson.title}",
            "",
            f"**Lesson ID:** `{lesson.lesson_id}`  ",
            f"**Estimated time:** {duration_minutes} minutes",
            "",
            lesson.summary.strip(),
            "",
            "## Learning objectives",
            "",
        ]

        lines.extend(f"- {objective}" for objective in objectives)

        for section in lesson.sections:
            lines.extend(
                [
                    "",
                    f"## {section.heading}",
                    "",
                    section.content.strip(),
                ]
            )
            if section.bullet_points:
                lines.append("")
                lines.extend(
                    f"- {point}" for point in section.bullet_points
                )

        if lesson.practical_activity is not None:
            activity = lesson.practical_activity
            lines.extend(
                [
                    "",
                    "## Practical activity",
                    "",
                    f"### {activity.title}",
                    "",
                    f"**Estimated time:** {activity.estimated_minutes} minutes",
                    "",
                ]
            )
            lines.extend(
                f"{index}. {instruction}"
                for index, instruction in enumerate(
                    activity.instructions,
                    start=1,
                )
            )
            if activity.expected_result:
                lines.extend(
                    [
                        "",
                        "**Expected result:**",
                        "",
                        activity.expected_result.strip(),
                    ]
                )

        lines.extend(["", "## Key takeaways", ""])
        lines.extend(
            f"- {takeaway}" for takeaway in lesson.key_takeaways
        )

        if lesson.instructor_notes:
            lines.extend(["", "## Instructor notes", ""])
            lines.extend(
                f"- {note}" for note in lesson.instructor_notes
            )

        if lesson.source_ids:
            lines.extend(["", "## Sources", ""])
            lines.extend(
                f"- `{source_id}`" for source_id in lesson.source_ids
            )

        return "\n".join(lines).rstrip() + "\n"

    def export(
        self,
        *,
        outline: CourseOutline,
        content: LessonContentSet,
        output_directory: str | Path,
    ) -> tuple[Path, ...]:
        output_directory = Path(output_directory)
        output_directory.mkdir(parents=True, exist_ok=True)

        planned = {
            lesson.lesson_id: lesson
            for module in outline.modules
            for lesson in module.lessons
        }

        exported: list[Path] = []
        index_lines = [
            f"# {outline.title}",
            "",
            f"**Audience:** {outline.audience}  ",
            f"**Language:** {outline.language}  ",
            f"**Total duration:** {outline.total_duration_minutes} minutes",
            "",
            "## Lessons",
            "",
        ]

        for number, lesson_content in enumerate(
            content.lessons,
            start=1,
        ):
            planned_lesson = planned[lesson_content.lesson_id]
            filename = f"{number:02d}_{_slug(planned_lesson.title)}.md"
            target = output_directory / filename
            target.write_text(
                self.render_lesson(
                    lesson=lesson_content,
                    objectives=planned_lesson.objectives,
                    duration_minutes=planned_lesson.duration_minutes,
                ),
                encoding="utf-8",
            )
            exported.append(target)
            index_lines.append(
                f"{number}. [{planned_lesson.title}]({filename})"
            )

        index_path = output_directory / "README.md"
        index_path.write_text(
            "\n".join(index_lines).rstrip() + "\n",
            encoding="utf-8",
        )

        return (index_path, *exported)
