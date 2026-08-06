from course_factory import (
    CourseModule,
    CourseOutline,
    ExerciseGenerationAgent,
    ExerciseMarkdownExporter,
    ExerciseSet,
    JobContext,
    Lesson,
    StaticJSONBackend,
)

def outline():
    return CourseOutline(
        title="Introduction to ggplot2",
        audience="Beginners",
        modules=(
            CourseModule(
                module_id="basics",
                title="Basics",
                lessons=(
                    Lesson(
                        lesson_id="scatter",
                        title="Scatter plots",
                        duration_minutes=30,
                        practical=True,
                        required_packages=("ggplot2",),
                        knowledge_ids=("DOC-1",),
                    ),
                ),
            ),
        ),
        learning_objectives=("Create plots",),
        required_packages=("ggplot2",),
        total_duration_minutes=60,
        references=("DOC-1",),
    )

def backend():
    return StaticJSONBackend(
        {
            "course_title": "Introduction to ggplot2",
            "exercises": [
                {
                    "exercise_id": "ex-scatter-1",
                    "lesson_id": "scatter",
                    "title": "Create a scatter plot",
                    "exercise_type": "code",
                    "instructions": "Create a scatter plot of Sepal.Length against Sepal.Width.",
                    "estimated_minutes": 15,
                    "difficulty": "beginner",
                    "starter_code": "library(ggplot2)\n# Add your ggplot code",
                    "hints": ["Use aes() and geom_point()."],
                    "expected_outputs": ["figures/ex-scatter-1.png"],
                    "required_packages": ["ggplot2"],
                    "knowledge_ids": ["DOC-1"],
                }
            ],
            "solutions": [
                {
                    "exercise_id": "ex-scatter-1",
                    "solution_text": "Map the two iris variables inside aes().",
                    "solution_code": (
                        "library(ggplot2)\n"
                        "ggplot(iris, aes(Sepal.Length, Sepal.Width)) + geom_point()"
                    ),
                    "explanation": "geom_point() creates one point per observation.",
                    "grading_points": ["Correct x and y mappings", "Uses geom_point()"],
                }
            ],
        }
    )

def test_exercise_generation_agent():
    context = JobContext.create(user_request="Create exercises").model_copy(
        update={
            "state": {
                "course_outline": outline().model_dump(mode="json"),
                "local_knowledge_results": [{"document_id": "DOC-1"}],
            }
        }
    )
    result = ExerciseGenerationAgent(backend()).run(context)
    assert result.status.value == "success"
    assert result.metrics["exercise_count"] == 1
    assert result.metrics["solution_count"] == 1

def test_markdown_export(tmp_path):
    context = JobContext.create(user_request="Create exercises").model_copy(
        update={"state": {"course_outline": outline().model_dump(mode="json")}}
    )
    result = ExerciseGenerationAgent(backend()).run(context)
    exercise_set = ExerciseSet.model_validate(result.outputs["exercise_set"])
    exercises, solutions = ExerciseMarkdownExporter().export(
        exercise_set,
        tmp_path,
    )
    assert exercises.exists()
    assert solutions.exists()
    assert "Create a scatter plot" in exercises.read_text(encoding="utf-8")
    assert "geom_point()" in solutions.read_text(encoding="utf-8")

def test_unsafe_starter_code_is_rejected():
    bad = StaticJSONBackend(
        {
            "course_title": "Introduction to ggplot2",
            "exercises": [
                {
                    "exercise_id": "bad",
                    "lesson_id": "scatter",
                    "title": "Unsafe exercise",
                    "exercise_type": "code",
                    "instructions": "Run the provided command and inspect the output.",
                    "estimated_minutes": 15,
                    "difficulty": "beginner",
                    "starter_code": 'system("curl https://example.com")',
                    "hints": [],
                    "expected_outputs": [],
                    "required_packages": [],
                    "knowledge_ids": [],
                }
            ],
            "solutions": [],
        }
    )
    context = JobContext.create(user_request="Create exercises").model_copy(
        update={"state": {"course_outline": outline().model_dump(mode="json")}}
    )
    result = ExerciseGenerationAgent(bad).run(context)
    assert result.status.value == "failed"
