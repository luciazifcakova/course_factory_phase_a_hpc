from pathlib import Path

from course_factory import JobContext
from course_factory.r_code_generation_agent import RCodeGenerationAgent
from course_factory.r_workflow_planner_agent import RWorkflowPlannerAgent
from course_factory.security_validator_agent import SecurityValidatorAgent


class StaticBackend:
    def generate_json(self, **kwargs):
        return {
            "code": (
                "library(ggplot2)\n"
                "dir.create('figures', recursive=TRUE, showWarnings=FALSE)\n"
                "p <- ggplot(iris, aes(Sepal.Length, Sepal.Width)) + geom_point()\n"
                "ggsave('figures/l1.png', p, width=7, height=5)"
            ),
            "expected_outputs": ["figures/l1.png"],
            "knowledge_ids": [],
        }


OUTLINE = {
    "title": "Introduction to ggplot2",
    "audience": "Beginners",
    "language": "English",
    "modules": [{
        "module_id": "m1",
        "title": "Plots",
        "description": "",
        "lessons": [{
            "lesson_id": "l1",
            "title": "Scatter plots",
            "duration_minutes": 60,
            "objectives": ["Create a scatter plot"],
            "practical": True,
            "requires_live_demo": True,
            "required_packages": ["ggplot2"],
            "prerequisites": [],
            "knowledge_ids": [],
        }],
        "prerequisites": [],
    }],
    "learning_objectives": ["Create a scatter plot"],
    "required_packages": ["ggplot2"],
    "total_duration_minutes": 60,
    "assumptions": [],
    "references": [],
    "version": "1.0",
}

LESSONS = {
    "course_title": "Introduction to ggplot2",
    "lessons": [{
        "lesson_id": "l1",
        "title": "Scatter plots",
        "summary": "This lesson explains how scatter plots show relationships.",
        "sections": [{
            "heading": "Core idea",
            "content": "Each point represents one observation using x and y positions.",
            "bullet_points": [],
        }],
        "key_takeaways": ["Scatter plots compare two numeric variables."],
        "practical_activity": {
            "title": "Create a plot",
            "instructions": ["Map variables to x and y."],
            "expected_result": "A scatter plot.",
            "estimated_minutes": 10,
        },
        "instructor_notes": [],
        "source_ids": [],
    }],
}


def test_workflow_generate_and_validate_r_script(tmp_path):
    context = JobContext.create(user_request="ggplot2").model_copy(
        update={"state": {
            "course_outline": OUTLINE,
            "lesson_content": LESSONS,
            "local_knowledge_results": [],
        }}
    )
    workflow = RWorkflowPlannerAgent().run(context)
    assert workflow.status.value == "success"
    context = context.with_result(workflow)

    generated = RCodeGenerationAgent(
        StaticBackend(), output_dir=tmp_path / "scripts"
    ).run(context)
    assert generated.status.value == "success"
    assert generated.metrics["generated_r_scripts"] == 1
    assert generated.metrics["failed_r_tasks"] == 0
    context = context.with_result(generated)

    security = SecurityValidatorAgent().run(context)
    assert security.status.value == "success"
    assert security.outputs["security_report"]["rejected_count"] == 0
    assert (tmp_path / "scripts" / "l1.R").is_file()
