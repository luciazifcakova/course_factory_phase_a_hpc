from __future__ import annotations

from pathlib import Path

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .job_context import JobContext
from .powerpoint_builder import PowerPointBuilder
from .slide_models import SlideDeck

class PowerPointBuilderAgent(Agent):
    name = "powerpoint_builder"
    version = "1.0.0"
    capabilities = frozenset({"powerpoint_building"})

    def __init__(
        self,
        *,
        builder: PowerPointBuilder | None = None,
        output_dir: str | Path = "workspace/presentations",
        artifact_root: str | Path = ".",
    ):
        self.builder = builder or PowerPointBuilder()
        self.output_dir = Path(output_dir)
        self.artifact_root = Path(artifact_root)

    def run(self, context: JobContext) -> AgentResult:
        outline_raw = context.state.get("course_outline")
        deck_raw = context.state.get("slide_deck")

        if not isinstance(outline_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_outline is missing",),
            )
        if not isinstance(deck_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("slide_deck is missing",),
            )

        try:
            outline = CourseOutline.model_validate(outline_raw)
            deck = SlideDeck.model_validate(deck_raw)
            filename = f"{context.job_id}_course.pptx"
            output_path = self.output_dir / filename

            report = self.builder.build(
                outline=outline,
                deck=deck,
                output_path=output_path,
                artifact_root=self.artifact_root,
            )
        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "presentation_report": report.model_dump(mode="json"),
                "presentation_path": report.output_path,
            },
            metrics={
                "presentation_slides": report.slide_count,
                "presentation_figures": report.figure_count,
                "presentation_code_blocks": report.code_block_count,
                "presentation_missing_artifacts": len(report.missing_artifacts),
            },
        )
