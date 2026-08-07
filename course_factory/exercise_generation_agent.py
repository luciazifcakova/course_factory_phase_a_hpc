from __future__ import annotations

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .exercise_models import ExerciseSet
from .exercise_validator import ExerciseValidator
from .job_context import JobContext
from .llm_backend import LLMBackend, ensure_structured_backend

EXERCISE_SCHEMA = '''{
  "course_title": "string",
  "exercises": [
    {
      "exercise_id": "string",
      "lesson_id": "string",
      "title": "string",
      "exercise_type": "code|interpretation|debugging|short_answer",
      "instructions": "string",
      "estimated_minutes": 15,
      "difficulty": "beginner",
      "starter_code": "string or null",
      "hints": ["string"],
      "expected_outputs": ["relative/path"],
      "required_packages": ["string"],
      "knowledge_ids": ["DOC-..."]
    }
  ],
  "solutions": [
    {
      "exercise_id": "string",
      "solution_text": "string",
      "solution_code": "string or null",
      "explanation": "string",
      "grading_points": ["string"]
    }
  ]
}'''

class ExerciseGenerationAgent(Agent):
    name = "exercise_generator"
    version = "1.0.0"
    capabilities = frozenset({"exercise_generation"})

    def __init__(self, backend: LLMBackend):
        self.backend = ensure_structured_backend(backend)
        self.validator = ExerciseValidator()

    def run(self, context: JobContext) -> AgentResult:
        outline_raw = context.state.get("course_outline")
        if not isinstance(outline_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_outline is missing",),
            )

        try:
            outline = CourseOutline.model_validate(outline_raw)
            knowledge = context.state.get("local_knowledge_results", [])
            exercise_set = self.backend.generate_structured(
                ExerciseSet,
                system=(
                    "You are an expert R instructor. Create practical exercises and "
                    "complete solutions aligned to the supplied lessons. Use only supplied "
                    "knowledge. Do not install packages, access the network, or use shell "
                    "commands. Use relative paths only."
                ),
                user=(
                    f"COURSE OUTLINE:\n{outline.model_dump_json(indent=2)}\n\n"
                    f"VALIDATED KNOWLEDGE:\n{knowledge}"
                ),
            )
            validation = self.validator.validate(
                outline=outline,
                exercise_set=exercise_set,
            )
            if not validation.ok:
                return AgentResult.failed(
                    agent_name=self.name,
                    errors=tuple(issue.message for issue in validation.issues),
                )

        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "exercise_set": exercise_set.model_dump(mode="json"),
                "exercise_validation": {
                    "ok": validation.ok,
                    "issues": [
                        {
                            "severity": issue.severity,
                            "code": issue.code,
                            "message": issue.message,
                            "exercise_id": issue.exercise_id,
                        }
                        for issue in validation.issues
                    ],
                },
            },
            metrics={
                "exercise_count": len(exercise_set.exercises),
                "solution_count": len(exercise_set.solutions),
                "exercise_warning_count": sum(
                    issue.severity == "warning" for issue in validation.issues
                ),
            },
        )
