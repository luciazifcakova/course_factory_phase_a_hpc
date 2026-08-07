from course_factory import (
    CoursePlannerAgent,
    JobContext,
)


SPEC = {
    "title": "Introduction to ggplot2",
    "topic": "ggplot2",
    "audience": "Beginners",
    "duration_minutes": 120,
    "language": "English",
    "delivery_mode": "online",
    "level": "beginner",
    "prerequisites": [
        "basic R programming knowledge"
    ],
    "learning_objectives": [
        "Create plots"
    ],
    "required_packages": ["ggplot2"],
    "exercise_count": 1,
    "assumptions": [],
    "clarification_required": False,
    "clarification_question": None,
}


VALID = {
    "modules": [
        {
            "module_id": "mod_001",
            "title": "Foundations",
            "description": "Core ideas",
            "prerequisite_module_ids": [],
            "lessons": [
                {
                    "lesson_id": "LES-001",
                    "title": "Grammar of graphics",
                    "duration_minutes": 60,
                    "objectives": [
                        "Explain mappings"
                    ],
                    "practical": True,
                    "requires_live_demo": True,
                    "required_packages": ["ggplot2"],
                    "prerequisite_lesson_ids": [],
                    "knowledge_ids": [],
                }
            ],
        },
        {
            "module_id": "mod_002",
            "title": "Applied plotting",
            "description": "Create plots",
            "prerequisite_module_ids": [
                "mod_001"
            ],
            "lessons": [
                {
                    "lesson_id": "LES-002",
                    "title": "Scatter plots",
                    "duration_minutes": 60,
                    "objectives": [
                        "Create scatter plots"
                    ],
                    "practical": True,
                    "requires_live_demo": True,
                    "required_packages": ["ggplot2"],
                    "prerequisite_lesson_ids": [
                        "LES-001"
                    ],
                    "knowledge_ids": [],
                }
            ],
        },
    ]
}


class SequenceBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(
        self,
        *,
        system,
        user,
        schema_hint,
    ):
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


def test_background_prerequisite_cannot_be_module_dependency(
    tmp_path,
):
    invalid = {
        "modules": [
            {
                "module_id": "mod_001",
                "title": "Foundations",
                "description": "Core ideas",
                "prerequisite_module_ids": [
                    "basic R programming knowledge"
                ],
                "lessons": [
                    {
                        "lesson_id": "LES-001",
                        "title": "Grammar of graphics",
                        "duration_minutes": 120,
                        "objectives": [
                            "Explain mappings"
                        ],
                        "practical": True,
                        "requires_live_demo": True,
                        "required_packages": ["ggplot2"],
                        "prerequisite_lesson_ids": [],
                        "knowledge_ids": [],
                    }
                ],
            }
        ]
    }

    backend = SequenceBackend(
        [invalid, VALID]
    )
    result = CoursePlannerAgent(
        backend,
        trace_dir=tmp_path / "planner",
        max_attempts=3,
    ).run(context())

    assert result.status.value == "success"
    assert backend.calls == 2
    assert result.metrics["planner_retries"] == 1
    assert (
        result.outputs["course_outline"]
        ["modules"][0]["prerequisites"]
        == []
    )


def test_unknown_dependency_id_is_repaired(
    tmp_path,
):
    invalid = {
        "modules": [
            {
                "module_id": "mod_001",
                "title": "Foundations",
                "description": "Core ideas",
                "prerequisite_module_ids": [
                    "mod_999"
                ],
                "lessons": [
                    {
                        "lesson_id": "LES-001",
                        "title": "Grammar of graphics",
                        "duration_minutes": 120,
                        "objectives": [
                            "Explain mappings"
                        ],
                        "practical": True,
                        "requires_live_demo": True,
                        "required_packages": ["ggplot2"],
                        "prerequisite_lesson_ids": [],
                        "knowledge_ids": [],
                    }
                ],
            }
        ]
    }

    result = CoursePlannerAgent(
        SequenceBackend([invalid, VALID]),
        trace_dir=tmp_path / "planner",
        max_attempts=3,
    ).run(context())

    assert result.status.value == "success"
    assert (
        result.outputs["course_outline"]
        ["modules"][1]["prerequisites"]
        == ["mod_001"]
    )


def test_planner_json_schema_uses_explicit_dependency_names():
    from course_factory.course_planner_agent import (
        PlannerResponse,
    )

    schema_text = str(
        PlannerResponse.model_json_schema()
    )

    assert "prerequisite_module_ids" in schema_text
    assert "prerequisite_lesson_ids" in schema_text


def test_legacy_prerequisites_alias_remains_accepted():
    # Existing tests/custom backends from earlier commits can still
    # return `prerequisites`, but production Ollama sees the explicit
    # *_ids schema names.
    legacy = {
        "modules": [
            {
                "module_id": "m1",
                "title": "Foundations",
                "description": "",
                "prerequisites": [],
                "lessons": [
                    {
                        "lesson_id": "l1",
                        "title": "Basics",
                        "duration_minutes": 120,
                        "objectives": [],
                        "practical": False,
                        "requires_live_demo": False,
                        "required_packages": [],
                        "prerequisites": [],
                        "knowledge_ids": [],
                    }
                ],
            }
        ]
    }

    result = CoursePlannerAgent(
        SequenceBackend([legacy])
    ).run(context())

    assert result.status.value == "success"
    assert (
        result.outputs["course_outline"]
        ["modules"][0]["module_id"]
        == "m1"
    )
