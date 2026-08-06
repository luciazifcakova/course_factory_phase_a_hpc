from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LessonSection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    heading: str = Field(min_length=2)
    content: str = Field(min_length=20)
    bullet_points: tuple[str, ...] = ()


class PracticalActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=2)
    instructions: tuple[str, ...] = ()
    expected_result: str = ""
    estimated_minutes: int = Field(default=10, ge=1, le=180)


class LessonContent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lesson_id: str = Field(min_length=1)
    title: str = Field(min_length=2)
    summary: str = Field(min_length=20)
    sections: tuple[LessonSection, ...] = Field(min_length=1)
    key_takeaways: tuple[str, ...] = Field(min_length=1)
    practical_activity: PracticalActivity | None = None
    instructor_notes: tuple[str, ...] = ()
    source_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_section_headings(self) -> "LessonContent":
        headings = [section.heading.casefold() for section in self.sections]
        if len(headings) != len(set(headings)):
            raise ValueError("Lesson section headings must be unique.")
        return self


class LessonContentSet(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    course_title: str = Field(min_length=3)
    lessons: tuple[LessonContent, ...]

    @model_validator(mode="after")
    def validate_unique_lesson_ids(self) -> "LessonContentSet":
        lesson_ids = [lesson.lesson_id for lesson in self.lessons]
        if len(lesson_ids) != len(set(lesson_ids)):
            raise ValueError("Lesson IDs must be unique.")
        return self
