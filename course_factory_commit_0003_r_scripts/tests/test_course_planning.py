import pytest

from course_factory import (
    CourseModule,
    CoursePlannerAgent,
    JobContext,
    Lesson,
    LessonScheduler,
    ModuleGraph,
    StaticJSONBackend,
)

def test_module_graph_orders_prerequisites():
    graph = ModuleGraph()
    graph.depends_on("ggplot2", "data_frames")
    graph.depends_on("data_frames", "vectors")
    order = graph.ordered_modules()
    assert order.index("vectors") < order.index("data_frames")
    assert order.index("data_frames") < order.index("ggplot2")

def test_module_graph_rejects_cycle():
    graph = ModuleGraph()
    graph.depends_on("a", "b")
    graph.depends_on("b", "a")
    with pytest.raises(ValueError):
        graph.ordered_modules()

def test_scheduler_orders_modules_and_tracks_free_time():
    modules = (
        CourseModule(
            module_id="ggplot2",
            title="ggplot2",
            prerequisites=("basics",),
            lessons=(
                Lesson(
                    lesson_id="plot",
                    title="Plotting",
                    duration_minutes=30,
                ),
            ),
        ),
        CourseModule(
            module_id="basics",
            title="Basics",
            lessons=(
                Lesson(
                    lesson_id="vectors",
                    title="Vectors",
                    duration_minutes=20,
                ),
            ),
        ),
    )
    result = LessonScheduler().schedule(
        modules=modules,
        total_duration_minutes=90,
    )
    assert result.modules[0].module_id == "basics"
    assert result.scheduled_minutes == 50
    assert result.unscheduled_minutes == 40

def test_course_planner_agent_builds_outline():
    backend = StaticJSONBackend(
        {
            "modules": [
                {
                    "module_id": "basics",
                    "title": "R basics",
                    "description": "Foundations",
                    "prerequisites": [],
                    "lessons": [
                        {
                            "lesson_id": "vectors",
                            "title": "Vectors",
                            "duration_minutes": 30,
                            "objectives": ["Create vectors"],
                            "practical": True,
                            "required_packages": [],
                            "knowledge_ids": ["DOC-1"],
                        }
                    ],
                },
                {
                    "module_id": "ggplot2",
                    "title": "ggplot2",
                    "description": "Visualization",
                    "prerequisites": ["basics"],
                    "lessons": [
                        {
                            "lesson_id": "scatter",
                            "title": "Scatter plots",
                            "duration_minutes": 45,
                            "objectives": ["Build a scatter plot"],
                            "practical": True,
                            "required_packages": ["ggplot2"],
                            "knowledge_ids": ["DOC-2"],
                        }
                    ],
                },
            ]
        }
    )
    agent = CoursePlannerAgent(backend)
    context = JobContext.create(user_request="Teach ggplot2").model_copy(
        update={
            "state": {
                "course_specification": {
                    "title": "Introduction to ggplot2",
                    "topic": "ggplot2",
                    "audience": "Beginners",
                    "duration_minutes": 120,
                    "language": "English",
                    "delivery_mode": "online",
                    "level": "beginner",
                    "prerequisites": [],
                    "learning_objectives": ["Create plots"],
                    "required_packages": ["ggplot2"],
                    "exercise_count": 2,
                    "assumptions": [],
                    "clarification_required": False,
                    "clarification_question": None,
                },
                "local_knowledge_results": [
                    {"document_id": "DOC-1"},
                    {"document_id": "DOC-2"},
                ],
            }
        }
    )
    result = agent.run(context)
    assert result.status.value == "success"
    outline = result.outputs["course_outline"]
    assert outline["modules"][0]["module_id"] == "basics"
    assert outline["modules"][1]["module_id"] == "ggplot2"
    assert "ggplot2" in outline["required_packages"]
    assert result.outputs["schedule_summary"]["scheduled_minutes"] == 75
