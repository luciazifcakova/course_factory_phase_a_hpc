from pathlib import Path

from course_factory import (
    ArtifactManifest,
    JobContext,
    LessonArtifactManifest,
    ManifestFile,
    SlideGenerationAgent,
    SlidePlannerAgent,
)


OUTLINE = {
    "title": "Introduction to ggplot2",
    "audience": "Scientists",
    "language": "English",
    "modules": [{
        "module_id": "mod_001",
        "title": "Plots",
        "description": "",
        "lessons": [{
            "lesson_id": "LES-001",
            "title": "Scatter plots",
            "duration_minutes": 45,
            "objectives": ["Create scatter plots"],
            "practical": True,
            "requires_live_demo": True,
            "required_packages": ["ggplot2"],
            "prerequisites": [],
            "knowledge_ids": [],
        }],
        "prerequisites": [],
    }],
    "learning_objectives": ["Create plots"],
    "required_packages": ["ggplot2"],
    "total_duration_minutes": 45,
    "assumptions": [],
    "references": [],
    "version": "1.0",
}

CONTENT = {
    "course_title": "Introduction to ggplot2",
    "lessons": [{
        "lesson_id": "LES-001",
        "title": "Scatter plots",
        "summary": (
            "This lesson introduces scatter plots for relationships "
            "between continuous variables."
        ),
        "sections": [{
            "heading": "Scatter plots",
            "content": (
                "A scatter plot maps two continuous variables to "
                "horizontal and vertical axes for comparison."
            ),
            "bullet_points": [],
        }],
        "key_takeaways": [
            "Use geom_point() for scatter plots."
        ],
        "practical_activity": {
            "title": "Build a scatter plot",
            "instructions": [
                "Map two variables and add geom_point()."
            ],
            "expected_result": "A scatter plot.",
            "estimated_minutes": 15,
        },
        "instructor_notes": [],
        "source_ids": [],
    }],
}


def manifest(tmp_path):
    script = tmp_path / "scripts" / "LES-001.R"
    figure = (
        tmp_path
        / "tasks"
        / "LES-001.r_code"
        / "output"
        / "figures"
        / "scatter.png"
    )
    script.parent.mkdir(parents=True)
    figure.parent.mkdir(parents=True)
    script.write_text("# R", encoding="utf-8")
    figure.write_bytes(b"png")

    return ArtifactManifest(
        job_id="job1",
        generated_at="2026-08-07T00:00:00+00:00",
        course_title="Introduction to ggplot2",
        lessons=(
            LessonArtifactManifest(
                lesson_id="LES-001",
                title="Scatter plots",
                script=ManifestFile(
                    relative_path="scripts/LES-001.R",
                    absolute_path=str(script),
                    content_type="text/x-r-source",
                    size_bytes=3,
                ),
                figures=(
                    ManifestFile(
                        relative_path=(
                            "tasks/LES-001.r_code/output/"
                            "figures/scatter.png"
                        ),
                        absolute_path=str(figure),
                        content_type="image/png",
                        size_bytes=3,
                    ),
                ),
                execution_status="completed",
            ),
        ),
        summary={},
    )


class SequenceBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def generate_json(
        self,
        *,
        system,
        user,
        schema_hint,
    ):
        self.calls += 1
        return self.responses.pop(0)


def base_context(tmp_path):
    return JobContext.create(
        user_request="Teach ggplot2"
    ).model_copy(
        update={
            "state": {
                "course_outline": OUTLINE,
                "lesson_content": CONTENT,
                "artifact_manifest": (
                    manifest(tmp_path).model_dump(
                        mode="json"
                    )
                ),
                "approved_r_scripts": [{
                    "task_id": "LES-001.r_code",
                    "lesson_id": "LES-001",
                    "relative_path": str(
                        tmp_path
                        / "scripts"
                        / "LES-001.R"
                    ),
                    "code": (
                        "library(ggplot2)\n"
                        "ggplot(mtcars, aes(wt, mpg)) "
                        "+ geom_point()"
                    ),
                    "required_packages": ["ggplot2"],
                    "expected_outputs": [
                        "figures/scatter.png"
                    ],
                    "output_contracts": [
                        "figures/*"
                    ],
                    "knowledge_ids": [],
                }],
            }
        }
    )


def valid_intent():
    return {
        "lesson_id": "LES-001",
        "lesson_title": "Scatter plots",
        "slides": [
            {"slide_id":"LES-001-S01","lesson_id":"LES-001","title":"Scatter plots","purpose":"Introduce the lesson and its goal.","kind":"overview","wants_visual":False,"wants_code":False},
            {"slide_id":"LES-001-S02","lesson_id":"LES-001","title":"Scatter example","purpose":"Explain geom_point with a worked visual.","kind":"example","wants_visual":True,"wants_code":False},
            {"slide_id":"LES-001-S03","lesson_id":"LES-001","title":"Try it","purpose":"Give learners a short practical task.","kind":"exercise","wants_visual":False,"wants_code":False},
        ],
    }


def valid_plan():
    return {
        "lesson_id": "LES-001",
        "lesson_title": "Scatter plots",
        "slides": [
            {
                "slide_id": "LES-001-S01",
                "lesson_id": "LES-001",
                "title": "Scatter plots",
                "purpose": (
                    "Introduce the lesson and its main goal."
                ),
                "layout": "title",
                "figure_artifacts": [],
                "use_code": False,
            },
            {
                "slide_id": "LES-001-S02",
                "lesson_id": "LES-001",
                "title": "Scatter plot example",
                "purpose": (
                    "Explain how geom_point maps two "
                    "continuous variables."
                ),
                "layout": "figure_bullets",
                "figure_artifacts": [
                    "tasks/LES-001.r_code/output/"
                    "figures/scatter.png"
                ],
                "use_code": False,
            },
            {
                "slide_id": "LES-001-S03",
                "lesson_id": "LES-001",
                "title": "Try it",
                "purpose": (
                    "Give learners a short practical task."
                ),
                "layout": "exercise",
                "figure_artifacts": [],
                "use_code": False,
            },
        ],
    }


def valid_text():
    return {
        "lesson_id": "LES-001",
        "slides": [
            {
                "slide_id": "LES-001-S01",
                "title": "Scatter plots",
                "bullets": [
                    "Visualize relationships between variables"
                ],
                "speaker_notes": (
                    "Introduce the grammar-of-graphics context."
                ),
            },
            {
                "slide_id": "LES-001-S02",
                "title": "A scatter plot in ggplot2",
                "bullets": [
                    "Map variables inside aes()",
                    "Add points with geom_point()",
                ],
                "speaker_notes": (
                    "Use the generated figure as the example."
                ),
            },
            {
                "slide_id": "LES-001-S03",
                "title": "Exercise",
                "bullets": [
                    "Choose two continuous variables",
                    "Create a scatter plot",
                ],
                "speaker_notes": (
                    "Give learners a few minutes to reproduce it."
                ),
            },
        ],
    }


def test_planner_resolves_figure_without_llm_path(tmp_path):
    backend = SequenceBackend([valid_intent()])
    result = SlidePlannerAgent(backend, trace_dir=tmp_path / "llm", max_attempts=3).run(base_context(tmp_path))
    assert result.status.value == "success"
    assert backend.calls == 1
    visual = result.outputs["slide_plan"]["lessons"][0]["slides"][1]
    assert visual["layout"] == "figure_bullets"
    assert visual["figure_artifacts"] == ["tasks/LES-001.r_code/output/figures/scatter.png"]


def test_slide_content_uses_fixed_plan_artifacts(
    tmp_path,
):
    context = base_context(tmp_path)
    context = context.model_copy(
        update={
            "state": {
                **context.state,
                "slide_plan": {
                    "course_title": (
                        "Introduction to ggplot2"
                    ),
                    "lessons": [
                        valid_plan()
                    ],
                },
            }
        }
    )

    result = SlideGenerationAgent(
        SequenceBackend([valid_text()]),
        output_dir=tmp_path / "slides",
        trace_dir=tmp_path / "llm",
    ).run(context)

    assert result.status.value == "success"
    deck = result.outputs["slide_deck"]
    assert len(deck["slides"]) == 3

    figure_slide = deck["slides"][1]
    assert figure_slide["figure_artifacts"] == [
        "tasks/LES-001.r_code/output/"
        "figures/scatter.png"
    ]
    assert figure_slide[
        "figure_artifact"
    ].endswith("scatter.png")
    assert (
        tmp_path / "slides" / "LES-001.json"
    ).is_file()


def test_slide_text_cannot_change_slide_ids(
    tmp_path,
):
    bad_text = valid_text()
    bad_text["slides"][1][
        "slide_id"
    ] = "SOMETHING-ELSE"

    context = base_context(tmp_path)
    context = context.model_copy(
        update={
            "state": {
                **context.state,
                "slide_plan": {
                    "course_title": (
                        "Introduction to ggplot2"
                    ),
                    "lessons": [
                        valid_plan()
                    ],
                },
            }
        }
    )

    backend = SequenceBackend(
        [bad_text, valid_text()]
    )
    result = SlideGenerationAgent(
        backend,
        output_dir=tmp_path / "slides",
        trace_dir=tmp_path / "llm",
        max_attempts=3,
    ).run(context)

    assert result.status.value == "success"
    assert backend.calls == 2
    assert result.metrics[
        "slide_content_retries"
    ] == 1
