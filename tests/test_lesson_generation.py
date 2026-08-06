from course_factory import (
    CourseOutline,
    JobContext,
    LessonContentSet,
    LessonGenerationAgent,
    LessonMarkdownRenderer,
)


class StaticSequenceBackend:
    def __init__(self, responses):
        self.responses = list(responses)

    def generate_json(self, **kwargs):
        return self.responses.pop(0)


SPECIFICATION = {
    "title": "Introduction to ggplot2",
    "topic": "ggplot2",
    "audience": "Beginners",
    "duration_minutes": 60,
    "language": "English",
    "delivery_mode": "online",
    "level": "beginner",
    "prerequisites": [],
    "learning_objectives": ["Create a scatter plot"],
    "required_packages": ["ggplot2"],
    "exercise_count": 1,
    "assumptions": [],
    "clarification_required": False,
    "clarification_question": None,
}


OUTLINE = {
    "title": "Introduction to ggplot2",
    "audience": "Beginners",
    "language": "English",
    "modules": [
        {
            "module_id": "m1",
            "title": "Plots",
            "description": "",
            "lessons": [
                {
                    "lesson_id": "l1",
                    "title": "Scatter plots",
                    "duration_minutes": 60,
                    "objectives": ["Create a scatter plot"],
                    "practical": True,
                    "requires_live_demo": True,
                    "required_packages": ["ggplot2"],
                    "prerequisites": [],
                    "knowledge_ids": ["DOC-1"],
                }
            ],
            "prerequisites": [],
        }
    ],
    "learning_objectives": ["Create a scatter plot"],
    "required_packages": ["ggplot2"],
    "total_duration_minutes": 60,
    "assumptions": [],
    "references": ["DOC-1"],
    "version": "1.0",
}


def valid_response():
    return {
        "lesson_id": "l1",
        "title": "Scatter plots",
        "summary": (
            "This lesson explains how scatter plots represent the "
            "relationship between numeric variables."
        ),
        "sections": [
            {
                "heading": "Core idea",
                "content": (
                    "Each point represents one observation positioned "
                    "according to its x and y values."
                ),
                "bullet_points": ["Use one point per observation."],
            }
        ],
        "key_takeaways": ["Points reveal numeric relationships."],
        "practical_activity": {
            "title": "Plan a scatter plot",
            "instructions": ["Choose x and y variables."],
            "expected_result": "A valid mapping plan.",
            "estimated_minutes": 10,
        },
        "instructor_notes": [],
        "source_ids": ["DOC-1"],
    }


def context():
    return JobContext.create(
        user_request="Create a ggplot2 course"
    ).model_copy(
        update={
            "state": {
                "course_specification": SPECIFICATION,
                "course_outline": OUTLINE,
            }
        }
    )


def test_lesson_agent_generates_valid_content():
    result = LessonGenerationAgent(
        StaticSequenceBackend([valid_response()])
    ).run(context())

    assert result.status.value == "success"
    assert result.metrics["generated_lesson_count"] == 1
    assert (
        result.outputs["lesson_content"]["lessons"][0]["lesson_id"]
        == "l1"
    )


def test_lesson_agent_rejects_unknown_source():
    response = valid_response()
    response["source_ids"] = ["DOC-UNKNOWN"]

    result = LessonGenerationAgent(
        StaticSequenceBackend([response])
    ).run(context())

    assert result.status.value == "failed"
    assert "unknown source IDs" in result.errors[0]


def test_markdown_renderer_exports_index_and_lesson(tmp_path):
    content = LessonContentSet.model_validate(
        {
            "course_title": "Introduction to ggplot2",
            "lessons": [valid_response()],
        }
    )
    paths = LessonMarkdownRenderer().export(
        outline=CourseOutline.model_validate(OUTLINE),
        content=content,
        output_directory=tmp_path / "lessons",
    )

    assert len(paths) == 2
    assert paths[0].name == "README.md"
    assert paths[1].name == "01_scatter-plots.md"
    assert "## Learning objectives" in paths[1].read_text(
        encoding="utf-8"
    )
