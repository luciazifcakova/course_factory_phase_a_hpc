from pathlib import Path


STRUCTURED_AGENT_FILES = (
    "input_builder_agent.py",
    "course_planner_agent.py",
    "lesson_generation_agent.py",
    "r_code_generation_agent.py",
    "slide_planner_agent.py",
    "slide_generation_agent.py",
)


def test_core_structured_agents_use_backend_structured_api():
    root = (
        Path(__file__).resolve().parents[1]
        / "course_factory"
    )

    for filename in STRUCTURED_AGENT_FILES:
        text = (root / filename).read_text(
            encoding="utf-8"
        )
        assert "generate_structured(" in text
