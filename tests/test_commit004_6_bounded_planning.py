import pytest
from pydantic import ValidationError

from course_factory import CoursePlannerAgent, JobContext
from course_factory.course_planner_agent import (
    PlannerModule,
    PlannerResponse,
)
from course_factory.course_specification import CourseSpecification


SPEC = {
    "title": "Introduction to ggplot2",
    "topic": "ggplot2",
    "audience": "Scientists new to R visualization",
    "duration_minutes": 180,
    "language": "English",
    "delivery_mode": "online",
    "level": "introductory",
    "prerequisites": [],
    "learning_objectives": [
        "Create basic ggplot2 visualizations",
        "Map variables to aesthetics",
        "Customize plots for scientific communication",
    ],
    "required_packages": ["ggplot2"],
    "exercise_count": 4,
    "assumptions": [],
    "clarification_required": False,
    "clarification_question": None,
}


GOOD = {
    "modules": [{
        "module_id": "mod_001",
        "title": "ggplot2 foundations",
        "description": "Core plotting",
        "prerequisite_module_ids": [],
        "lessons": [
            {
                "lesson_id": "LES-001",
                "title": "Grammar of graphics",
                "duration_minutes": 45,
                "objectives": ["Explain aesthetics"],
                "practical": True,
                "requires_live_demo": True,
                "required_packages": ["ggplot2"],
                "prerequisite_lesson_ids": [],
                "knowledge_ids": [],
            },
            {
                "lesson_id": "LES-002",
                "title": "Scatter plots",
                "duration_minutes": 45,
                "objectives": ["Create scatter plots"],
                "practical": True,
                "requires_live_demo": True,
                "required_packages": ["ggplot2"],
                "prerequisite_lesson_ids": ["LES-001"],
                "knowledge_ids": [],
            },
            {
                "lesson_id": "LES-003",
                "title": "Distributions",
                "duration_minutes": 45,
                "objectives": ["Create distribution plots"],
                "practical": True,
                "requires_live_demo": True,
                "required_packages": ["ggplot2"],
                "prerequisite_lesson_ids": ["LES-002"],
                "knowledge_ids": [],
            },
            {
                "lesson_id": "LES-004",
                "title": "Themes",
                "duration_minutes": 45,
                "objectives": ["Customize plots"],
                "practical": True,
                "requires_live_demo": True,
                "required_packages": ["ggplot2"],
                "prerequisite_lesson_ids": ["LES-003"],
                "knowledge_ids": [],
            },
        ],
    }]
}


class SequenceBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, *, system, user, schema_hint):
        self.calls += 1
        return self.responses.pop(0)


def context():
    return JobContext.create(
        user_request="Create a ggplot2 course"
    ).model_copy(
        update={
            "state": {
                "course_specification": SPEC,
                "local_knowledge_results": [],
            }
        }
    )


def test_empty_learning_objectives_rejected():
    payload = dict(SPEC)
    payload["learning_objectives"] = []
    with pytest.raises(ValidationError):
        CourseSpecification.model_validate(payload)


def test_empty_module_rejected():
    with pytest.raises(ValidationError):
        PlannerModule.model_validate({
            "module_id": "mod_001",
            "title": "Empty",
            "lessons": [],
            "prerequisite_module_ids": [],
        })


def test_more_than_eight_modules_rejected():
    payload = {
        "modules": [
            {
                "module_id": f"mod_{i:03d}",
                "title": f"Module {i}",
                "lessons": [{
                    "lesson_id": f"LES-{i:03d}",
                    "title": f"Lesson {i}",
                    "duration_minutes": 20,
                    "objectives": [],
                    "practical": False,
                    "requires_live_demo": False,
                    "required_packages": [],
                    "prerequisite_lesson_ids": [],
                    "knowledge_ids": [],
                }],
                "prerequisite_module_ids": [],
            }
            for i in range(1, 10)
        ]
    }
    with pytest.raises(ValidationError):
        PlannerResponse.model_validate(payload)


def test_underfilled_plan_retries(tmp_path):
    bad = {
        "modules": [{
            "module_id": "mod_001",
            "title": "Tiny",
            "lessons": [{
                "lesson_id": "LES-001",
                "title": "Short",
                "duration_minutes": 30,
                "objectives": [],
                "practical": True,
                "requires_live_demo": True,
                "required_packages": ["ggplot2"],
                "prerequisite_lesson_ids": [],
                "knowledge_ids": [],
            }],
            "prerequisite_module_ids": [],
        }]
    }

    backend = SequenceBackend([bad, GOOD])
    result = CoursePlannerAgent(
        backend,
        trace_dir=tmp_path,
        max_attempts=3,
    ).run(context())

    assert result.status.value == "success"
    assert backend.calls == 2
    assert result.metrics["planner_retries"] == 1


def test_repair_prompt_is_bounded():
    prompt = CoursePlannerAgent._repair_prompt(
        original_user="original",
        error="bad",
        previous_response={
            "_raw_content": "x" * 100_000
        },
    )
    assert len(prompt) < 5000
    assert "previous response truncated" in prompt


def test_json_schema_has_hard_array_limits():
    schema = PlannerResponse.model_json_schema()
    modules = schema["properties"]["modules"]
    assert modules["minItems"] == 1
    assert modules["maxItems"] == 8

    lessons = schema[
        "$defs"
    ]["PlannerModule"]["properties"]["lessons"]
    assert lessons["minItems"] == 1
    assert lessons["maxItems"] == 8
