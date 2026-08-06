from course_factory import EvidenceFusionAgent, JobContext, KnowledgeAssessmentAgent, StaticJSONBackend

SPEC = {
    "title":"Introduction to ggplot2","topic":"ggplot2","audience":"Beginners",
    "duration_minutes":120,"language":"English","delivery_mode":"online",
    "level":"beginner","prerequisites":[],"learning_objectives":["Create scatter plots"],
    "required_packages":["ggplot2"],"exercise_count":2,"assumptions":[],
    "clarification_required":False,"clarification_question":None
}

def test_fusion_counts_duplicates():
    backend = StaticJSONBackend({
        "topics":[{
            "topic":"ggplot2 grammar",
            "summary":"ggplot2 uses a layered grammar of graphics.",
            "supporting_documents":["DOC-1","DOC-2"],
            "conflicting_documents":[],
            "confidence":0.95,
            "unresolved_questions":[]
        }],
        "source_document_count":99,
        "unique_document_count":99,
        "duplicate_document_ids":[]
    })
    ctx = JobContext.create(user_request="Teach ggplot2").model_copy(update={"state":{
        "local_knowledge_results":[
            {"document_id":"DOC-1"},{"document_id":"DOC-1"},{"document_id":"DOC-2"}
        ]
    }})
    result = EvidenceFusionAgent(backend).run(ctx)
    fused = result.outputs["fused_evidence"]
    assert fused["source_document_count"] == 3
    assert fused["unique_document_count"] == 2
    assert fused["duplicate_document_ids"] == ["DOC-1"]

def test_assessment_outputs_queries():
    backend = StaticJSONBackend({
        "sufficient":False,
        "confidence":0.8,
        "covered_topics":["scatter plots"],
        "missing_topics":["themes"],
        "suggested_queries":["official ggplot2 themes documentation"],
        "explanation":"Themes are not covered by the available evidence."
    })
    ctx = JobContext.create(user_request="Teach ggplot2").model_copy(update={"state":{
        "course_specification":SPEC,
        "fused_evidence":{
            "topics":[],
            "source_document_count":0,
            "unique_document_count":0,
            "duplicate_document_ids":[]
        }
    }})
    result = KnowledgeAssessmentAgent(backend).run(ctx)
    assert result.outputs["knowledge_assessment"]["sufficient"] is False
    assert result.outputs["knowledge_search_queries"] == ["official ggplot2 themes documentation"]
