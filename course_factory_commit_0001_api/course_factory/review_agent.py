from __future__ import annotations
from .agent import Agent
from .agent_result import AgentResult
from .content_reviewer import SlideDeckReviewer, ExerciseSetReviewer
from .job_context import JobContext

class ReviewAgent(Agent):
    name = "content_reviewer"
    capabilities = frozenset({"content_review"})

    def __init__(self):
        self.slide_reviewer = SlideDeckReviewer()
        self.exercise_reviewer = ExerciseSetReviewer()

    def run(self, context: JobContext) -> AgentResult:
        slides = context.state.get("slide_deck")
        exercises = context.state.get("exercise_set")
        if not isinstance(slides, dict) or not isinstance(exercises, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("slide_deck or exercise_set is missing",),
            )

        slide_report = self.slide_reviewer.review(slides)
        exercise_report = self.exercise_reviewer.review(exercises)
        passed = slide_report.passed and exercise_report.passed
        score = (slide_report.score + exercise_report.score) / 2

        return AgentResult.success(
            agent_name=self.name,
            outputs={"content_review": {
                "passed": passed,
                "score": score,
                "slide_deck": slide_report.model_dump(mode="json"),
                "exercise_set": exercise_report.model_dump(mode="json"),
            }},
            metrics={"content_review_passed": passed, "content_review_score": score},
        )
