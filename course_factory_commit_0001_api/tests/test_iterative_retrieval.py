from course_factory import (
    DocumentDeduplicator,
    IterativeRetrievalAgent,
    JobContext,
    RetrievalPlanner,
    RetrievalSource,
    StaticSearchBackend,
)
from course_factory.evidence_models import KnowledgeAssessment


def assessment():
    return {
        "sufficient": False,
        "confidence": 0.75,
        "covered_topics": ["scatter plots"],
        "missing_topics": ["themes"],
        "suggested_queries": [
            "official ggplot2 themes documentation",
        ],
        "explanation": (
            "The evidence does not cover complete theme customization."
        ),
    }


def test_retrieval_planner_builds_stable_task():
    model = KnowledgeAssessment.model_validate(assessment())
    tasks = RetrievalPlanner().build(
        model,
        source=RetrievalSource.WEB,
    )

    assert len(tasks) == 1
    assert tasks[0].query == "official ggplot2 themes documentation"
    assert tasks[0].topic == "themes"
    assert tasks[0].task_id.startswith("retrieve-")


def test_iterative_retrieval_merges_filtered_results():
    backend = StaticSearchBackend(
        {
            "official ggplot2 themes documentation": [
                {
                    "result_id": "WEB-1",
                    "title": "Complete themes",
                    "url": "https://ggplot2.tidyverse.org/reference/complete_themes.html",
                    "source_type": "official_doc",
                    "content": (
                        "Official documentation for complete ggplot2 themes "
                        "including theme_bw() and theme_minimal()."
                    ),
                    "quality_score": 0.55,
                },
                {
                    "result_id": "WEB-2",
                    "title": "Complete themes",
                    "url": "https://ggplot2.tidyverse.org/reference/complete_themes.html",
                    "source_type": "official_doc",
                    "content": (
                        "Official documentation for complete ggplot2 themes "
                        "including theme_bw() and theme_minimal()."
                    ),
                    "quality_score": 0.55,
                },
            ]
        }
    )
    context = JobContext.create(user_request="Teach ggplot2").model_copy(
        update={
            "state": {
                "knowledge_assessment": assessment(),
                "local_knowledge_results": [
                    {
                        "document_id": "LOCAL-1",
                        "title": "Scatter plots",
                        "topic": "scatter plots",
                        "source": "local",
                        "source_type": "official_doc",
                        "content": "Use geom_point() for scatter plots.",
                        "score": 0.9,
                        "quality_score": 0.9,
                        "metadata": {},
                    }
                ],
            }
        }
    )

    result = IterativeRetrievalAgent(backend=backend).run(context)

    assert result.status.value == "success"
    assert result.metrics["iterative_retrieval_results"] == 1
    assert result.metrics["iterative_retrieval_duplicates"] == 1
    merged = result.outputs["local_knowledge_results"]
    assert len(merged) == 2
    assert merged[-1]["document_id"] == "WEB-1"


def test_document_deduplicator_keeps_distinct_content():
    from course_factory import SearchResult

    results = (
        SearchResult(
            result_id="A",
            query="q",
            title="One",
            source=RetrievalSource.WEB,
            source_type="article",
            topic="R",
            content="First document.",
            quality_score=0.8,
        ),
        SearchResult(
            result_id="B",
            query="q",
            title="Two",
            source=RetrievalSource.WEB,
            source_type="article",
            topic="R",
            content="Second document.",
            quality_score=0.8,
        ),
    )

    unique, duplicates = DocumentDeduplicator().deduplicate(results)

    assert len(unique) == 2
    assert duplicates == 0
