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
        {
            "lesson_id": "l1",
            "title": "Grammar of graphics",
            "summary": (
                "This lesson introduces the layered grammar used by "
                "ggplot2 to construct visualizations."
            ),
            "sections": [
                {
                    "heading": "Layers of a plot",
                    "content": (
                        "A ggplot2 graphic combines data, aesthetic "
                        "mappings and geometric objects in explicit layers."
                    ),
                    "bullet_points": [
                        "Data supplies observations.",
                        "Aesthetics connect variables to visual properties.",
                    ],
                }
            ],
            "key_takeaways": [
                "A ggplot2 plot is assembled from composable layers."
            ],
            "practical_activity": {
                "title": "Identify plot components",
                "instructions": [
                    "Inspect a simple ggplot2 expression.",
                    "Identify its data, mappings and geometry.",
                ],
                "expected_result": (
                    "The learner correctly labels each plot component."
                ),
                "estimated_minutes": 15,
            },
            "instructor_notes": [
                "Use a simple iris example during discussion."
            ],
            "source_ids": [],
        },
        {
            "lesson_id": "l2",
            "title": "Scatter plots",
            "summary": (
                "This lesson develops scatter plots and explains common "
                "aesthetic mappings and customizations."
            ),
            "sections": [
                {
                    "heading": "Building a scatter plot",
                    "content": (
                        "Scatter plots display the relationship between "
                        "two numeric variables using points."
                    ),
                    "bullet_points": [
                        "Map numeric variables to x and y.",
                        "Use colour carefully to represent groups.",
                    ],
                }
            ],
            "key_takeaways": [
                "geom_point creates a scatter-plot layer."
            ],
            "practical_activity": {
                "title": "Design a scatter plot",
                "instructions": [
                    "Choose two numeric variables from iris.",
                    "Describe the mappings and expected visual pattern.",
                ],
                "expected_result": (
                    "A clear plan for a labelled scatter plot."
                ),
                "estimated_minutes": 20,
            },
            "instructor_notes": [],
            "source_ids": [],
        },
        {
            "code": (
                "library(ggplot2)\n"
                "dir.create('figures', recursive=TRUE, showWarnings=FALSE)\n"
                "p <- ggplot(iris, aes(Sepal.Length, Sepal.Width)) + geom_point()\n"
                "ggsave('figures/l1.png', p, width=7, height=5)"
            ),
            "expected_outputs": ["figures/l1.png"],
            "knowledge_ids": [],
        },
        {
            "code": (
                "library(ggplot2)\n"
                "dir.create('figures', recursive=TRUE, showWarnings=FALSE)\n"
                "p <- ggplot(iris, aes(Sepal.Length, Petal.Length, colour=Species)) + geom_point()\n"
                "ggsave('figures/l2.png', p, width=7, height=5)"
            ),
            "expected_outputs": ["figures/l2.png"],
            "knowledge_ids": [],
        },
    ]


def test_api_creates_specification_outline_and_lessons(tmp_path):
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
    assert result.current_step == "r_scripts_complete"
    assert len(result.artifacts) == 15

    job_dir = tmp_path / "workspace" / "jobs" / "job_test"
    assert (job_dir / "course_specification.json").is_file()
    assert (job_dir / "course_outline.json").is_file()
    assert (job_dir / "lesson_content.json").is_file()
    assert (job_dir / "lessons" / "README.md").is_file()
    assert (
        job_dir / "lessons" / "01_grammar-of-graphics.md"
    ).is_file()
    assert (
        job_dir / "lessons" / "02_scatter-plots.md"
    ).is_file()
    assert (job_dir / "workflow_plan.json").is_file()
    assert (job_dir / "r_code_generation_report.json").is_file()
    assert (job_dir / "security_report.json").is_file()
    assert (job_dir / "scripts" / "l1.R").is_file()
    assert (job_dir / "scripts" / "l2.R").is_file()

    lesson_text = (
        job_dir / "lessons" / "01_grammar-of-graphics.md"
    ).read_text(encoding="utf-8")
    assert "# Grammar of graphics" in lesson_text
    assert "## Practical activity" in lesson_text
    assert "## Key takeaways" in lesson_text

    stored = api.get_job("job_test")
    assert stored["status"] == "completed"
    assert stored["state"]["course_outline"]["title"] == (
        "Introduction to ggplot2"
    )
    assert len(stored["state"]["lesson_content"]["lessons"]) == 2

    event_messages = [
        event["message"]
        for event in api.get_events("job_test")
    ]
    assert "Course specification created." in event_messages
    assert (
        "Course lessons and security-approved R scripts created successfully."
    ) in event_messages


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
