from __future__ import annotations

from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)


class SlideLayout(StrEnum):
    TITLE = "title"
    BULLETS = "bullets"
    FIGURE = "figure"
    FIGURE_BULLETS = "figure_bullets"
    CODE = "code"
    EXERCISE = "exercise"
    SUMMARY = "summary"


class SlideIntentKind(StrEnum):
    OVERVIEW = "overview"
    CONCEPT = "concept"
    EXAMPLE = "example"
    CODE_EXAMPLE = "code_example"
    EXERCISE = "exercise"
    SUMMARY = "summary"


class SlideIntentItem(BaseModel):
    """LLM-facing educational intent; no layout or artifact paths."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    slide_id: str = Field(min_length=1, max_length=80)
    lesson_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=2, max_length=120)
    purpose: str = Field(min_length=5, max_length=300)
    kind: SlideIntentKind = SlideIntentKind.CONCEPT
    wants_visual: bool = False
    wants_code: bool = False

    @model_validator(mode="after")
    def validate_intent(self) -> "SlideIntentItem":
        if self.kind is SlideIntentKind.CODE_EXAMPLE and not self.wants_code:
            raise ValueError("code_example intent requires wants_code=true")
        if self.kind is not SlideIntentKind.CODE_EXAMPLE and self.wants_code:
            raise ValueError("wants_code=true is only valid for code_example intent")
        return self


class LessonSlideIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    lesson_id: str = Field(min_length=1)
    lesson_title: str = Field(min_length=2)
    slides: tuple[SlideIntentItem, ...] = Field(min_length=2, max_length=12)

    @model_validator(mode="after")
    def validate_ids(self) -> "LessonSlideIntent":
        ids = [slide.slide_id for slide in self.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("slide_id values must be unique within a lesson")
        if any(slide.lesson_id != self.lesson_id for slide in self.slides):
            raise ValueError("all slide intents must use the parent lesson_id")
        return self


class SlidePlanItem(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    slide_id: str = Field(min_length=1, max_length=80)
    lesson_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=2, max_length=120)
    purpose: str = Field(min_length=5, max_length=300)
    layout: SlideLayout
    figure_artifacts: tuple[str, ...] = Field(
        default=(),
        max_length=2,
    )
    # The LLM only chooses whether a code slide is useful.
    # Python resolves the exact script path from artifact_manifest.json.
    use_code: bool = False

    @model_validator(mode="after")
    def validate_layout_artifacts(
        self,
    ) -> "SlidePlanItem":
        figure_layouts = {
            SlideLayout.FIGURE,
            SlideLayout.FIGURE_BULLETS,
        }
        if (
            self.layout in figure_layouts
            and not self.figure_artifacts
        ):
            raise ValueError(
                f"{self.layout.value} slide requires "
                "at least one figure_artifact"
            )
        if (
            self.layout not in figure_layouts
            and self.figure_artifacts
        ):
            raise ValueError(
                f"{self.layout.value} slide must not "
                "reference figures"
            )
        if (
            self.layout is SlideLayout.CODE
            and not self.use_code
        ):
            raise ValueError(
                "code slide requires use_code=true"
            )
        if (
            self.layout is not SlideLayout.CODE
            and self.use_code
        ):
            raise ValueError(
                "use_code=true is only valid for code layout"
            )
        return self


class LessonSlidePlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    lesson_id: str = Field(min_length=1)
    lesson_title: str = Field(min_length=2)
    slides: tuple[SlidePlanItem, ...] = Field(
        min_length=2,
        max_length=12,
    )

    @model_validator(mode="after")
    def validate_ids(self) -> "LessonSlidePlan":
        ids = [
            slide.slide_id
            for slide in self.slides
        ]
        if len(ids) != len(set(ids)):
            raise ValueError(
                "slide_id values must be unique "
                "within a lesson"
            )
        if any(
            slide.lesson_id != self.lesson_id
            for slide in self.slides
        ):
            raise ValueError(
                "all slides must use the parent lesson_id"
            )
        return self


class CourseSlidePlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    course_title: str = Field(min_length=3)
    lessons: tuple[LessonSlidePlan, ...] = Field(
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_unique_ids(
        self,
    ) -> "CourseSlidePlan":
        lesson_ids = [
            lesson.lesson_id
            for lesson in self.lessons
        ]
        if len(lesson_ids) != len(set(lesson_ids)):
            raise ValueError(
                "lesson IDs in slide plan must be unique"
            )

        slide_ids = [
            slide.slide_id
            for lesson in self.lessons
            for slide in lesson.slides
        ]
        if len(slide_ids) != len(set(slide_ids)):
            raise ValueError(
                "slide IDs must be globally unique"
            )
        return self


class SlideText(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    slide_id: str = Field(min_length=1)
    title: str = Field(min_length=2, max_length=120)
    bullets: tuple[str, ...] = Field(
        default=(),
        max_length=5,
    )
    speaker_notes: str = Field(
        default="",
        max_length=4000,
    )


class LessonSlideText(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    lesson_id: str = Field(min_length=1)
    slides: tuple[SlideText, ...] = Field(
        min_length=2,
        max_length=12,
    )


class Slide(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    slide_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    title: str = Field(min_length=2)
    bullets: tuple[str, ...] = Field(
        default=(),
        max_length=5,
    )
    speaker_notes: str = ""
    references: tuple[str, ...] = ()
    code_artifact: str | None = None

    # Legacy single-figure field remains for the existing PPT builder.
    figure_artifact: str | None = None

    # Commit 005 canonical representation.
    figure_artifacts: tuple[str, ...] = Field(
        default=(),
        max_length=2,
    )
    layout: SlideLayout = SlideLayout.BULLETS


class LessonSlideDeck(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    lesson_id: str = Field(min_length=1)
    lesson_title: str = Field(min_length=2)
    slides: tuple[Slide, ...] = Field(
        min_length=2,
        max_length=12,
    )


class SlideDeck(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    course_title: str = Field(min_length=3)
    slides: tuple[Slide, ...]
    lessons: tuple[LessonSlideDeck, ...] = ()

    @model_validator(mode="after")
    def validate_unique_ids(self):
        ids = [
            slide.slide_id
            for slide in self.slides
        ]
        if len(ids) != len(set(ids)):
            raise ValueError(
                "slide_id values must be unique"
            )
        return self


class SlideGenerationAttempt(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    agent: str
    lesson_id: str
    attempt: int = Field(ge=1)
    succeeded: bool
    request_path: str
    response_path: str | None = None
    validation_errors: tuple[str, ...] = ()


class SlideGenerationReport(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    lesson_count: int = Field(ge=0)
    slide_count: int = Field(ge=0)
    slides_with_figures: int = Field(ge=0)
    slides_with_code: int = Field(ge=0)
    planner_attempts: int = Field(ge=0)
    content_attempts: int = Field(ge=0)
    retries: int = Field(ge=0)
    attempts: tuple[
        SlideGenerationAttempt,
        ...,
    ] = ()
