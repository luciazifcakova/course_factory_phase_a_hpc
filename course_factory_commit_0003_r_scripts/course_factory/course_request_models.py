from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateCourseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str = Field(min_length=3)
    title: str | None = None
    audience: str | None = None
    duration_minutes: int | None = Field(
        default=None,
        ge=15,
        le=2880,
    )
    language: str | None = None
    level: str | None = None
    required_packages: tuple[str, ...] = ()
    output_formats: tuple[str, ...] = (
        "course_specification",
        "course_outline",
    )

    @model_validator(mode="after")
    def validate_output_formats(self) -> "CreateCourseRequest":
        allowed = {
            "course_specification",
            "course_outline",
        }
        unknown = set(self.output_formats) - allowed
        if unknown:
            raise ValueError(
                "Unsupported output formats: "
                + ", ".join(sorted(unknown))
            )
        return self

    def effective_prompt(self) -> str:
        details = []
        if self.title:
            details.append(f"Preferred title: {self.title}")
        if self.audience:
            details.append(f"Audience: {self.audience}")
        if self.duration_minutes:
            details.append(
                f"Duration: {self.duration_minutes} minutes"
            )
        if self.language:
            details.append(f"Language: {self.language}")
        if self.level:
            details.append(f"Level: {self.level}")
        if self.required_packages:
            details.append(
                "Required R packages: "
                + ", ".join(self.required_packages)
            )

        if not details:
            return self.prompt

        return self.prompt.rstrip() + "\n\n" + "\n".join(details)
