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
                    "lesson_id": "LES-002",
                    "title": "Scatter plots and line charts",
                    "duration_minutes": 60,
                    "objectives": [
                        "Create scatter and line plots"
                    ],
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
    "learning_objectives": [
        "Create scatter and line plots"
    ],
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
            "task_id": "LES-002.r_code",
            "task_type": "r_script",
            "lesson_id": "LES-002",
            "description": "Generate code",
            "input_artifacts": [],
            "output_artifacts": ["scripts/LES-002.R"],
            "depends_on": [],
            "required_packages": ["ggplot2"],
            "estimated_minutes": 5,
            "max_retries": 2,
        },
        {
            "task_id": "LES-002.figure",
            "task_type": "figure",
            "lesson_id": "LES-002",
            "description": "Generate figures",
            "input_artifacts": ["scripts/LES-002.R"],
            "output_artifacts": ["figures/*.png"],
            "depends_on": ["LES-002.r_code"],
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
            "lesson_id": "LES-002",
            "title": "Scatter plots and line charts",
            "summary": (
                "This lesson compares scatter plots and line charts."
            ),
            "sections": [
                {
                    "heading": "Plot types",
                    "content": (
                        "Scatter plots show relationships while line "
                        "charts emphasize ordered trajectories."
                    ),
                    "bullet_points": [],
                }
            ],
            "key_takeaways": [
                "Use the plot type appropriate to the data."
            ],
            "practical_activity": {
                "title": "Create two plots",
                "instructions": [
                    "Create one scatter plot and one line chart."
                ],
                "expected_result": "Two PNG figures.",
                "estimated_minutes": 15,
            },
            "instructor_notes": [],
            "source_ids": [],
        }
    ],
}


CODE = '''library(ggplot2)
dir.create("figures", recursive=TRUE, showWarnings=FALSE)
p1 <- ggplot(mtcars, aes(wt, mpg)) + geom_point()
ggsave("figures/scatter_plot.png", p1)
d <- data.frame(x=1:5, y=c(1,3,2,5,4))
p2 <- ggplot(d, aes(x, y)) + geom_line()
ggsave("figures/line_chart.png", p2)
'''


class StaticBackend:
    def __init__(self, response):
        self.response = response

    def generate_json(self, **kwargs):
        return self.response


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


def test_multiple_figures_are_accepted(tmp_path):
    result = RCodeGenerationAgent(
        StaticBackend(
            {
                "code": CODE,
                "expected_outputs": [
                    "figures/scatter_plot.png",
                    "figures/line_chart.png",
                ],
                "knowledge_ids": [],
            }
        ),
        output_dir=tmp_path / "scripts",
        trace_dir=tmp_path / "llm",
    ).run(context())

    assert result.status.value == "success"
    report = result.outputs[
        "r_code_generation_report"
    ]
    assert report["failed_task_ids"] == []
    assert report["scripts"][0]["expected_outputs"] == [
        "figures/scatter_plot.png",
        "figures/line_chart.png",
    ]


def test_output_outside_contract_is_rejected(tmp_path):
    result = RCodeGenerationAgent(
        StaticBackend(
            {
                "code": CODE.replace(
                    "figures/scatter_plot.png",
                    "tables/scatter_plot.csv",
                ),
                "expected_outputs": [
                    "tables/scatter_plot.csv",
                    "figures/line_chart.png",
                ],
                "knowledge_ids": [],
            }
        ),
        output_dir=tmp_path / "scripts",
        trace_dir=tmp_path / "llm",
        max_attempts=1,
    ).run(context())

    report = result.outputs[
        "r_code_generation_report"
    ]
    assert report["failed_task_ids"] == [
        "LES-002.r_code"
    ]
    assert "outside the workflow contracts" in (
        report["failure_reasons"]["LES-002.r_code"][0]
    )


def test_workflow_planner_uses_figure_collection_contract():
    from course_factory.r_workflow_planner_agent import (
        RWorkflowPlannerAgent,
    )

    result = RWorkflowPlannerAgent().run(
        JobContext.create(
            user_request="Create a course"
        ).model_copy(
            update={
                "state": {
                    "course_outline": OUTLINE
                }
            }
        )
    )

    plan = result.outputs["workflow_plan"]
    figure_tasks = [
        task
        for task in plan["tasks"]
        if task["task_type"] == "figure"
    ]
    assert figure_tasks[0]["output_artifacts"] == [
        "figures/*.png"
    ]
