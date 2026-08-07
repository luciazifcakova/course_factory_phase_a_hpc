from __future__ import annotations

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .job_context import JobContext
from .llm_backend import LLMBackend, ensure_structured_backend
from .slide_models import SlideDeck

SLIDE_SCHEMA = '''{
  "course_title": "string",
  "slides": [
    {
      "slide_id": "string",
      "lesson_id": "string",
      "title": "string",
      "bullets": ["string"],
      "speaker_notes": "string",
      "references": ["DOC-..."],
      "code_artifact": "scripts/example.R or null",
      "figure_artifact": "figures/example.png or null"
    }
  ]
}'''

class SlideContentAgent(Agent):
    name = "slide_content"
    version = "1.0.0"
    capabilities = frozenset({"slide_generation"})

    def __init__(self, backend: LLMBackend):
        self.backend = ensure_structured_backend(backend)

    def run(self, context: JobContext) -> AgentResult:
        outline_raw = context.state.get("course_outline")
        workflow_raw = context.state.get("workflow_plan")
        if not isinstance(outline_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_outline is missing",),
            )
        if not isinstance(workflow_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("workflow_plan is missing",),
            )

        try:
            outline = CourseOutline.model_validate(outline_raw)
            knowledge = context.state.get("local_knowledge_results", [])
            deck = self.backend.generate_structured(
                SlideDeck,
                system=(
                    "You are an expert R instructor. Generate concise teaching slides. "
                    "Every factual statement must be supported by supplied knowledge. "
                    "Use at most five bullets per slide. Preserve lesson IDs and references."
                ),
                user=(
                    f"COURSE OUTLINE:\n{outline.model_dump_json(indent=2)}\n\n"
                    f"WORKFLOW PLAN:\n{workflow_raw}\n\n"
                    f"KNOWLEDGE:\n{knowledge}"
                ),
            )
            valid_lesson_ids = {
                lesson.lesson_id
                for module in outline.modules
                for lesson in module.lessons
            }
            unknown = {
                slide.lesson_id
                for slide in deck.slides
                if slide.lesson_id not in valid_lesson_ids
            }
            if unknown:
                raise ValueError(f"slides reference unknown lessons: {sorted(unknown)}")

        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={"slide_deck": deck.model_dump(mode="json")},
            metrics={
                "slides": len(deck.slides),
                "slides_with_code": sum(
                    slide.code_artifact is not None for slide in deck.slides
                ),
                "slides_with_figures": sum(
                    slide.figure_artifact is not None for slide in deck.slides
                ),
            },
        )
