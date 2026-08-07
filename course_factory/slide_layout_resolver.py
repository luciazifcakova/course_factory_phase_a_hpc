from __future__ import annotations

from pathlib import Path

from .job_artifacts import LessonArtifactManifest
from .slide_models import (
    LessonSlideIntent,
    LessonSlidePlan,
    SlideIntentKind,
    SlideLayout,
    SlidePlanItem,
)


class SlideLayoutResolver:
    """Deterministically resolve slide intent into layout and artifacts."""

    @staticmethod
    def _ordered_figures(lesson_manifest: LessonArtifactManifest) -> list[str]:
        figures = list(lesson_manifest.figures)
        figures.sort(
            key=lambda item: (
                0 if Path(item.relative_path).suffix.lower() == ".png" else 1,
                item.relative_path,
            )
        )
        return [item.relative_path for item in figures]

    @classmethod
    def resolve(
        cls,
        *,
        intent: LessonSlideIntent,
        lesson_manifest: LessonArtifactManifest,
    ) -> LessonSlidePlan:
        figures = cls._ordered_figures(lesson_manifest)
        used: set[str] = set()
        script_available = lesson_manifest.script is not None
        resolved: list[SlidePlanItem] = []

        for index, slide in enumerate(intent.slides):
            layout = SlideLayout.BULLETS
            figure_artifacts: tuple[str, ...] = ()
            use_code = False

            if index == 0 or slide.kind is SlideIntentKind.OVERVIEW:
                layout = SlideLayout.TITLE
            elif slide.kind is SlideIntentKind.EXERCISE:
                layout = SlideLayout.EXERCISE
            elif slide.kind is SlideIntentKind.SUMMARY:
                layout = SlideLayout.SUMMARY
            elif slide.kind is SlideIntentKind.CODE_EXAMPLE and script_available:
                layout = SlideLayout.CODE
                use_code = True
            else:
                wants_figure = slide.wants_visual or slide.kind is SlideIntentKind.EXAMPLE
                candidate = next((p for p in figures if p not in used), None)
                if wants_figure and candidate is not None:
                    layout = SlideLayout.FIGURE_BULLETS
                    figure_artifacts = (candidate,)
                    used.add(candidate)

            resolved.append(
                SlidePlanItem(
                    slide_id=slide.slide_id,
                    lesson_id=slide.lesson_id,
                    title=slide.title,
                    purpose=slide.purpose,
                    layout=layout,
                    figure_artifacts=figure_artifacts,
                    use_code=use_code,
                )
            )

        # Unused figures remain available as supplementary artifacts.
        # We do not create extra slides solely to consume every file; slide
        # count and educational intent remain governed by the lesson plan.

        return LessonSlidePlan(
            lesson_id=intent.lesson_id,
            lesson_title=intent.lesson_title,
            slides=tuple(resolved),
        )
