from course_factory import JobContext
from course_factory.lesson_generation_agent import (
    LessonGenerationAgent,
)

SPECIFICATION = {
    "title": "Introduction to ggplot2",
    "topic": "ggplot2",
    "audience": "Beginners",
    "duration_minutes": 60,
    "language": "English",
    "delivery_mode": "online",
    "level": "beginner",
    "prerequisites": [],
    "learning_objectives": ["Create basic plots"],
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
    "modules": [{
        "module_id": "M1",
        "title": "Plots",
        "description": "Plotting",
        "lessons": [{
            "lesson_id": "LES-005",
            "title": "Troubleshooting",
            "duration_minutes": 60,
            "objectives": ["Recognize common plotting errors"],
            "practical": True,
            "requires_live_demo": True,
            "required_packages": ["ggplot2"],
            "prerequisites": [],
            "knowledge_ids": [],
        }],
        "prerequisites": [],
    }],
    "learning_objectives": ["Recognize common plotting errors"],
    "required_packages": ["ggplot2"],
    "total_duration_minutes": 60,
    "assumptions": [],
    "references": [],
    "version": "1.0",
}

VALID = {
    "lesson_id": "LES-005",
    "title": "Troubleshooting",
    "summary": "This lesson explains common plotting mistakes and how to diagnose them.",
    "sections": [{
        "heading": "Common mistakes",
        "content": "Learners inspect simple plotting mistakes and identify the source of each problem.",
        "bullet_points": [],
    }],
    "key_takeaways": ["Read errors carefully before changing code."],
    "practical_activity": {
        "title": "Diagnose a broken plot",
        "instructions": ["Inspect the error and correct the code."],
        "expected_result": "A corrected plot.",
        "estimated_minutes": 15,
    },
    "instructor_notes": [],
    "source_ids": [],
}

class SequenceBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
    def generate_json(self, **kwargs):
        self.calls += 1
        return self.responses.pop(0)

def context():
    return JobContext.create(
        user_request="Create a course"
    ).model_copy(update={
        "state": {
            "course_specification": SPECIFICATION,
            "course_outline": OUTLINE,
        }
    })

def test_malformed_lesson_structure_is_repaired(tmp_path):
    malformed = {
        "lesson_id": "LES-005",
        "title": "Troubleshooting",
        "summary": "This lesson explains common plotting problems.",
        "sections": [
            {
                "heading": "Common mistakes",
                "content": "Learners inspect common plotting mistakes.",
                "bullet_points": [],
            },
            "key_takeaways': [",
        ],
        "practical_activity": {
            "title": "Diagnose a plot",
            "instructions": ["Fix it."],
            "expected_result": "A working plot.",
            "estimated_minutes": 15,
        },
        "instructor_notes": [],
        "source_ids": [],
    }
    backend = SequenceBackend([malformed, VALID])
    result = LessonGenerationAgent(
        backend,
        trace_dir=tmp_path / "llm",
        max_attempts=3,
    ).run(context())
    assert result.status.value == "success"
    assert backend.calls == 2
    assert result.metrics["retried_lessons"] == 1
    lesson_dir = tmp_path / "llm" / "LES-005"
    assert (lesson_dir / "attempt_01_response.json").is_file()
    assert (lesson_dir / "attempt_01_validation.json").is_file()
    assert (lesson_dir / "attempt_02_response.json").is_file()
    assert (lesson_dir / "result.json").is_file()
