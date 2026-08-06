from pathlib import Path

from course_factory import JobContext
from course_factory.r_code_generation_agent import (
    RCodeGenerationAgent,
)


OUTLINE = {
    "title": "Introduction to ggplot2",
    "audience": "Beginners",
    "language": "English",
    "modules": [
        {
            "module_id": "M1",
            "title": "Plots",
            "description": "Plotting",
            "lessons": [
                {
                    "lesson_id": "LES-001",
                    "title": "Scatter plots",
                    "duration_minutes": 60,
                    "objectives": ["Create a scatter plot"],
                    "practical": True,
                    "requires_live_demo": True,
                    "required_packages": ["ggplot2"],
                    "prerequisites": [],
                    "knowledge_ids": [],
                }
            ],
            "prerequisites": [],
        }
    ],
    "learning_objectives": ["Create a scatter plot"],
    "required_packages": ["ggplot2"],
    "total_duration_minutes": 60,
    "assumptions": [],
    "references": [],
    "version": "1.0",
}


PLAN = {
    "course_title": "Introduction to ggplot2",
    "tasks": [
        {
            "task_id": "LES-001.r_code",
            "task_type": "r_script",
            "lesson_id": "LES-001",
            "description": "Generate R code",
            "input_artifacts": [],
            "output_artifacts": ["scripts/LES-001.R"],
            "depends_on": [],
            "required_packages": ["ggplot2"],
            "estimated_minutes": 5,
            "max_retries": 2,
        },
        {
            "task_id": "LES-001.figure",
            "task_type": "figure",
            "lesson_id": "LES-001",
            "description": "Generate figure",
            "input_artifacts": ["scripts/LES-001.R"],
            "output_artifacts": ["figures/LES-001.png"],
            "depends_on": ["LES-001.r_code"],
            "required_packages": ["ggplot2"],
            "estimated_minutes": 3,
            "max_retries": 2,
        },
    ],
    "version": "1.0",
}


LESSON_CONTENT = {
    "course_title": "Introduction to ggplot2",
    "lessons": [
        {
            "lesson_id": "LES-001",
            "title": "Scatter plots",
            "summary": (
                "This lesson introduces scatter plots using ggplot2."
            ),
            "sections": [
                {
                    "heading": "Plot construction",
                    "content": (
                        "A scatter plot maps two numeric variables "
                        "to horizontal and vertical position."
                    ),
                    "bullet_points": [],
                }
            ],
            "key_takeaways": [
                "geom_point creates a point layer."
            ],
            "practical_activity": {
                "title": "Create a scatter plot",
                "instructions": ["Plot iris variables."],
                "expected_result": "A PNG scatter plot.",
                "estimated_minutes": 15,
            },
            "instructor_notes": [],
            "source_ids": [],
        }
    ],
}


def context():
    return JobContext.create(
        user_request="Create a ggplot2 course"
    ).model_copy(
        update={
            "state": {
                "course_outline": OUTLINE,
                "workflow_plan": PLAN,
                "lesson_content": LESSON_CONTENT,
                "local_knowledge_results": [],
            }
        }
    )


VALID_CODE = '''dir.create(
  "figures",
  recursive = TRUE,
  showWarnings = FALSE
)
library(ggplot2)
p <- ggplot(iris, aes(Sepal.Length, Petal.Length)) +
  geom_point()
ggsave("figures/LES-001.png", p)
'''


class SequenceBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(self, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def test_accepts_script_alias_and_canonicalizes_code(tmp_path):
    backend = SequenceBackend(
        [
            {
                "script": VALID_CODE,
                "expected_outputs": [
                    "figures/LES-001.png"
                ],
                "knowledge_ids": [],
            }
        ]
    )

    result = RCodeGenerationAgent(
        backend,
        output_dir=tmp_path / "scripts",
        trace_dir=tmp_path / "llm",
    ).run(context())

    assert result.status.value == "success"
    assert result.metrics["generated_r_scripts"] == 1
    assert (
        result.outputs["generated_r_scripts"][0]["code"].strip()
        == VALID_CODE.strip()
    )


def test_missing_code_is_retried_and_raw_response_is_saved(
    tmp_path,
):
    backend = SequenceBackend(
        [
            {
                "expected_outputs": [
                    "figures/LES-001.png"
                ],
                "knowledge_ids": [],
            },
            {
                "code": VALID_CODE,
                "expected_outputs": [
                    "figures/LES-001.png"
                ],
                "knowledge_ids": [],
            },
        ]
    )

    result = RCodeGenerationAgent(
        backend,
        output_dir=tmp_path / "scripts",
        trace_dir=tmp_path / "llm",
        max_attempts=3,
    ).run(context())

    assert result.status.value == "success"
    assert backend.calls == 2
    assert result.metrics["r_generation_retries"] == 1

    task_dir = tmp_path / "llm" / "LES-001.r_code"
    assert (
        task_dir / "attempt_01_response.json"
    ).is_file()
    assert (
        task_dir / "attempt_02_response.json"
    ).is_file()

    attempts = result.outputs[
        "r_code_generation_report"
    ]["attempts"]
    assert attempts[0]["succeeded"] is False
    assert "code" in attempts[0]["validation_errors"][0]
    assert attempts[1]["succeeded"] is True


def test_all_failed_attempts_create_report_and_progress(tmp_path):
    backend = SequenceBackend(
        [
            {"not_code": "x"},
            {"still_not_code": "y"},
        ]
    )

    result = RCodeGenerationAgent(
        backend,
        output_dir=tmp_path / "scripts",
        trace_dir=tmp_path / "llm",
        max_attempts=2,
    ).run(context())

    report = result.outputs[
        "r_code_generation_report"
    ]
    assert result.status.value == "success"
    assert report["failed_task_ids"] == [
        "LES-001.r_code"
    ]
    assert report["generated_count"] == 0
    assert (
        tmp_path / "r_code_generation_progress.json"
    ).is_file()


def test_markdown_code_fence_is_removed(tmp_path):
    backend = SequenceBackend(
        [
            {
                "code": "```r\n"
                + VALID_CODE
                + "\n```",
                "expected_outputs": [
                    "figures/LES-001.png"
                ],
                "knowledge_ids": [],
            }
        ]
    )

    result = RCodeGenerationAgent(
        backend,
        output_dir=tmp_path / "scripts",
        trace_dir=tmp_path / "llm",
    ).run(context())

    code = result.outputs[
        "generated_r_scripts"
    ][0]["code"]
    assert not code.startswith("```")
    assert code.strip() == VALID_CODE.strip()
