from course_factory import (
    CourseFactoryAPI,
    CreateCourseRequest,
    HPCSettings,
)


class SequenceBackend:
    def __init__(self, responses):
        self.responses = list(responses)

    def generate_json(self, *, system, user, schema_hint):
        if not self.responses:
            raise AssertionError("Unexpected LLM call")
        return self.responses.pop(0)


def settings(tmp_path):
    return HPCSettings(
        workspace=tmp_path / "workspace",
        apptainer_image=None,
        allowed_r_packages=("base", "ggplot2"),
        slurm_partition="cpu",
        slurm_cpus=2,
        slurm_memory_gb=8,
        slurm_time_minutes=60,
        slurm_poll_seconds=1,
        slurm_wait_seconds=60,
        local_timeout_seconds=60,
        ollama_base_url="http://127.0.0.1:11434",
        ollama_model="qwen3:14b",
        ollama_timeout_seconds=60,
    )


def responses():
    return [
        {
            "title": "Introduction to ggplot2",
            "topic": "ggplot2",
            "audience": "Scientists new to visualization",
            "duration_minutes": 180,
            "language": "English",
            "delivery_mode": "online",
            "level": "beginner",
            "prerequisites": ["Basic R syntax"],
            "learning_objectives": [
                "Explain the grammar of graphics",
                "Create scatter plots with ggplot2",
            ],
            "required_packages": ["ggplot2"],
            "exercise_count": 2,
            "assumptions": [],
            "clarification_required": False,
            "clarification_question": None,
        },
        {
            "modules": [
                {
                    "module_id": "m1",
                    "title": "ggplot2 foundations",
                    "description": "Core grammar and first plots.",
                    "prerequisites": [],
                    "lessons": [
                        {
                            "lesson_id": "l1",
                            "title": "Grammar of graphics",
                            "duration_minutes": 60,
                            "objectives": [
                                "Explain mappings and geometries"
                            ],
                            "practical": True,
                            "requires_live_demo": True,
                            "required_packages": ["ggplot2"],
                            "prerequisites": [],
                            "knowledge_ids": [],
                        },
                        {
                            "lesson_id": "l2",
                            "title": "Scatter plots",
                            "duration_minutes": 120,
                            "objectives": [
                                "Build and customize scatter plots"
                            ],
                            "practical": True,
                            "requires_live_demo": True,
                            "required_packages": ["ggplot2"],
                            "prerequisites": ["l1"],
                            "knowledge_ids": [],
                        },
                    ],
                }
            ]
        },
    ]


def test_api_creates_specification_and_outline(tmp_path):
    api = CourseFactoryAPI(
        settings=settings(tmp_path),
        backend=SequenceBackend(responses()),
    )

    result = api.create_course(
        CreateCourseRequest(
            prompt="Create an introduction to ggplot2 course",
            duration_minutes=180,
            required_packages=("ggplot2",),
        ),
        job_id="job_test",
    )

    assert result.status == "completed"
    assert result.current_step == "outline_complete"
    assert len(result.artifacts) == 2

    job_dir = tmp_path / "workspace" / "jobs" / "job_test"
    assert (job_dir / "course_specification.json").is_file()
    assert (job_dir / "course_outline.json").is_file()

    stored = api.get_job("job_test")
    assert stored["status"] == "completed"
    assert stored["state"]["course_outline"]["title"] == (
        "Introduction to ggplot2"
    )

    event_messages = [
        event["message"]
        for event in api.get_events("job_test")
    ]
    assert "Course specification created." in event_messages
    assert "Course outline created successfully." in event_messages


def test_api_accepts_plain_text_request(tmp_path):
    api = CourseFactoryAPI(
        settings=settings(tmp_path),
        backend=SequenceBackend(responses()),
    )

    result = api.create_course(
        "Create an introduction to ggplot2 course",
        job_id="job_text",
    )

    assert result.status == "completed"


def test_api_records_failed_llm_call(tmp_path):
    class BrokenBackend:
        def generate_json(self, **kwargs):
            raise RuntimeError("Ollama unavailable")

    api = CourseFactoryAPI(
        settings=settings(tmp_path),
        backend=BrokenBackend(),
    )

    result = api.create_course(
        "Create a course",
        job_id="job_failed",
    )

    assert result.status == "failed"
    assert "Ollama unavailable" in result.errors[0]
    stored = api.get_job("job_failed")
    assert stored["status"] == "failed"
