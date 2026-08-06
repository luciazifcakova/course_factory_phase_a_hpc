from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

class Slide(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    slide_id: str = Field(min_length=1)
    lesson_id: str = Field(min_length=1)
    title: str = Field(min_length=2)
    bullets: tuple[str, ...] = ()
    speaker_notes: str = ""
    references: tuple[str, ...] = ()
    code_artifact: str | None = None
    figure_artifact: str | None = None

class SlideDeck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    course_title: str = Field(min_length=3)
    slides: tuple[Slide, ...]

    @model_validator(mode="after")
    def validate_unique_ids(self):
        ids = [slide.slide_id for slide in self.slides]
        if len(ids) != len(set(ids)):
            raise ValueError("slide_id values must be unique")
        return self
