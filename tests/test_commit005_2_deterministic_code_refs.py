from course_factory.slide_models import LessonSlidePlan


def test_code_slide_uses_boolean_not_path():
    plan = LessonSlidePlan.model_validate({
        "lesson_id": "LES-001",
        "lesson_title": "Example",
        "slides": [
            {
                "slide_id": "LES-001-S01",
                "lesson_id": "LES-001",
                "title": "Overview",
                "purpose": "Introduce the lesson.",
                "layout": "title",
                "figure_artifacts": [],
                "use_code": False,
            },
            {
                "slide_id": "LES-001-S02",
                "lesson_id": "LES-001",
                "title": "Code",
                "purpose": "Show the executable example.",
                "layout": "code",
                "figure_artifacts": [],
                "use_code": True,
            },
        ],
    })
    assert plan.slides[1].use_code is True
    schema = str(LessonSlidePlan.model_json_schema())
    assert "use_code" in schema
    assert "code_artifact" not in schema


def test_non_code_slide_cannot_request_code():
    try:
        LessonSlidePlan.model_validate({
            "lesson_id": "LES-001",
            "lesson_title": "Example",
            "slides": [
                {
                    "slide_id": "LES-001-S01",
                    "lesson_id": "LES-001",
                    "title": "Overview",
                    "purpose": "Introduce the lesson.",
                    "layout": "title",
                    "figure_artifacts": [],
                    "use_code": True,
                },
                {
                    "slide_id": "LES-001-S02",
                    "lesson_id": "LES-001",
                    "title": "Summary",
                    "purpose": "Summarize the lesson.",
                    "layout": "summary",
                    "figure_artifacts": [],
                    "use_code": False,
                },
            ],
        })
    except Exception as exc:
        assert "use_code=true is only valid" in str(exc)
    else:
        raise AssertionError("non-code slide should not request code")
