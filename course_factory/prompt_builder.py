from __future__ import annotations

INPUT_BUILDER_PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = (
    "You are an input builder for R training courses. Convert short requests into "
    "a structured course specification. Infer sensible defaults. Preserve explicit "
    "duration, audience, package and level constraints. Ask for clarification only "
    "when the actual topic or package is ambiguous."
)

SCHEMA_HINT = '''{
  "title": "string",
  "topic": "string",
  "audience": "string",
  "duration_minutes": 180,
  "language": "English",
  "delivery_mode": "online",
  "level": "beginner",
  "prerequisites": ["string"],
  "learning_objectives": ["string"],
  "required_packages": ["string"],
  "exercise_count": 4,
  "assumptions": ["string"],
  "clarification_required": false,
  "clarification_question": null
}'''

def build_input_builder_prompt(user_request: str) -> tuple[str, str, str]:
    return SYSTEM_PROMPT, user_request, SCHEMA_HINT
