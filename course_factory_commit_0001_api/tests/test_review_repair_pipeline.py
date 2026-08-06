from course_factory import JobContext, ReviewAgent, RepairAgent, StaticJSONBackend

def valid_exercises():
    return {
        "course_title":"R",
        "exercises":[{
            "exercise_id":"ex1","lesson_id":"l1","title":"Create a vector",
            "exercise_type":"code","instructions":"Create a numeric vector.",
            "estimated_minutes":10,"difficulty":"beginner",
            "starter_code":"x <- c()","hints":[],"expected_outputs":[],
            "required_packages":[],"knowledge_ids":["DOC-1"]
        }],
        "solutions":[{
            "exercise_id":"ex1","solution_text":"Use c().",
            "solution_code":"x <- c(1,2,3)","explanation":"c() combines values.",
            "grading_points":["Creates a vector"]
        }]
    }

def valid_slides():
    return {
        "course_title":"R",
        "slides":[{
            "slide_id":"s1","lesson_id":"l1","title":"Vectors",
            "bullets":["Use c() to create vectors."],
            "speaker_notes":"","references":["DOC-1"],
            "code_artifact":None,"figure_artifact":None
        }]
    }

def test_review_passes_valid_content():
    ctx = JobContext.create(user_request="Review").model_copy(update={"state":{
        "slide_deck":valid_slides(),"exercise_set":valid_exercises()
    }})
    result = ReviewAgent().run(ctx)
    assert result.outputs["content_review"]["passed"] is True

def test_repair_updates_broken_exercises():
    broken = valid_exercises()
    broken["solutions"] = []
    review = ReviewAgent().run(
        JobContext.create(user_request="Review").model_copy(update={"state":{
            "slide_deck":valid_slides(),"exercise_set":broken
        }})
    ).outputs["content_review"]

    backend = StaticJSONBackend({
        "artifact_name":"exercise_set",
        "repaired_payload":valid_exercises(),
        "change_summary":["Added missing solution."],
        "attempt":1
    })
    ctx = JobContext.create(user_request="Repair").model_copy(update={"state":{
        "slide_deck":valid_slides(),"exercise_set":broken,"content_review":review
    }})
    result = RepairAgent(backend).run(ctx)
    assert result.outputs["exercise_set"]["solutions"]
