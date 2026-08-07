from course_factory.slide_models import LessonSlideIntent


def test_code_intent_uses_boolean_not_path():
    intent = LessonSlideIntent.model_validate({
        "lesson_id": "LES-001", "lesson_title": "Example", "slides": [
            {"slide_id":"LES-001-S01","lesson_id":"LES-001","title":"Overview","purpose":"Introduce the lesson.","kind":"overview","wants_visual":False,"wants_code":False},
            {"slide_id":"LES-001-S02","lesson_id":"LES-001","title":"Code","purpose":"Show the executable example.","kind":"code_example","wants_visual":False,"wants_code":True},
        ]})
    assert intent.slides[1].wants_code is True
    schema = LessonSlideIntent.model_json_schema()
    properties = schema["$defs"]["SlideIntentItem"]["properties"]
    assert "wants_code" in properties
    assert "code_artifact" not in properties
    assert "figure_artifacts" not in properties
    assert "layout" not in properties
