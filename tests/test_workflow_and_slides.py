from course_factory import (
    JobContext,
    RWorkflowPlannerAgent,
    SlideContentAgent,
    StaticJSONBackend,
)

OUTLINE = {
    "title": "Introduction to ggplot2",
    "audience": "Beginners",
    "language": "English",
    "modules": [
        {
            "module_id": "basics",
            "title": "Basics",
            "description": "",
            "prerequisites": [],
            "lessons": [
                {
                    "lesson_id": "scatter",
                    "title": "Scatter plots",
                    "duration_minutes": 30,
                    "objectives": ["Create a scatter plot"],
                    "practical": True,
                    "requires_live_demo": True,
                    "required_packages": ["ggplot2"],
                    "prerequisites": [],
                    "knowledge_ids": ["DOC-1"],
                }
            ],
        }
    ],
    "learning_objectives": ["Create plots"],
    "required_packages": ["ggplot2"],
    "total_duration_minutes": 60,
    "assumptions": [],
    "references": ["DOC-1"],
    "version": "1.0",
}

def test_workflow_planner_builds_code_figure_and_slide_tasks():
    context = JobContext.create(user_request="Teach ggplot2").model_copy(
        update={"state": {"course_outline": OUTLINE}}
    )
    result = RWorkflowPlannerAgent().run(context)
    assert result.status.value == "success"
    plan = result.outputs["workflow_plan"]
    assert len(plan["tasks"]) == 3
    assert {task["task_type"] for task in plan["tasks"]} == {
        "r_script", "figure", "slide_content"
    }

def test_slide_content_agent_builds_valid_deck():
    workflow = RWorkflowPlannerAgent().run(
        JobContext.create(user_request="Teach ggplot2").model_copy(
            update={"state": {"course_outline": OUTLINE}}
        )
    ).outputs["workflow_plan"]

    backend = StaticJSONBackend(
        {
            "course_title": "Introduction to ggplot2",
            "slides": [
                {
                    "slide_id": "scatter-1",
                    "lesson_id": "scatter",
                    "title": "Scatter plots",
                    "bullets": [
                        "Use geom_point() for scatter plots",
                        "Map variables inside aes()",
                    ],
                    "speaker_notes": "Demonstrate with iris.",
                    "references": ["DOC-1"],
                    "code_artifact": "scripts/scatter.R",
                    "figure_artifact": "figures/*",
                }
            ],
        }
    )
    context = JobContext.create(user_request="Teach ggplot2").model_copy(
        update={
            "state": {
                "course_outline": OUTLINE,
                "workflow_plan": workflow,
                "local_knowledge_results": [{"document_id": "DOC-1"}],
            }
        }
    )
    result = SlideContentAgent(backend).run(context)
    assert result.status.value == "success"
    assert result.metrics["slides"] == 1
    assert result.metrics["slides_with_figures"] == 1
