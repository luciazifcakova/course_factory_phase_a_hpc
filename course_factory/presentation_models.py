from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

class PresentationTheme(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = "default"
    title_font: str = "Aptos Display"
    body_font: str = "Aptos"
    code_font: str = "Consolas"
    title_font_size_pt: int = Field(default=28, ge=18, le=44)
    body_font_size_pt: int = Field(default=20, ge=12, le=32)
    code_font_size_pt: int = Field(default=14, ge=8, le=24)
    footer_text: str = ""
    aspect_ratio: str = "16:9"

class PresentationBuildReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    output_path: str
    slide_count: int
    figure_count: int
    code_block_count: int
    missing_artifacts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
