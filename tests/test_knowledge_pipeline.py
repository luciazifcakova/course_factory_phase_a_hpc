from course_factory import (
    EmbeddingBackend,
    EmbeddingService,
    InMemoryVectorStore,
    KnowledgeRetrieverAgent,
    KnowledgeStore,
    LocalKnowledgeRetriever,
    JobContext,
)

class FakeEmbeddingBackend(EmbeddingBackend):
    def embed(self, text: str) -> list[float]:
        text = text.lower()
        return [
            1.0 if "ggplot" in text else 0.0,
            1.0 if "theme" in text else 0.0,
            1.0 if "facet" in text else 0.0,
            0.5,
        ]

def build_retriever(tmp_path):
    store = KnowledgeStore(tmp_path / "knowledge.sqlite3")
    vectors = InMemoryVectorStore()
    embeddings = EmbeddingService(FakeEmbeddingBackend())
    return LocalKnowledgeRetriever(
        metadata_store=store,
        vector_store=vectors,
        embeddings=embeddings,
    )

def test_index_and_semantic_retrieve(tmp_path):
    retriever = build_retriever(tmp_path)
    retriever.index_document(
        document_id="DOC-1",
        title="ggplot2 themes",
        source="ggplot2 website",
        source_type="official_doc",
        topic="ggplot2",
        content="Themes control the non-data components of a ggplot.",
        quality_score=0.95,
    )
    results = retriever.retrieve("ggplot themes", topic="ggplot2")
    assert len(results) == 1
    assert results[0].document_id == "DOC-1"
    assert results[0].score > 0.8

def test_duplicate_document_is_not_reindexed(tmp_path):
    retriever = build_retriever(tmp_path)
    first = retriever.index_document(
        document_id="DOC-1",
        title="ggplot2",
        source="official",
        source_type="official_doc",
        topic="ggplot2",
        content="Grammar of graphics",
    )
    second = retriever.index_document(
        document_id="DOC-2",
        title="ggplot2",
        source="official",
        source_type="official_doc",
        topic="ggplot2",
        content="Grammar of graphics",
    )
    assert first[1] is True
    assert second[1] is False

def test_retriever_agent_reports_insufficient_knowledge(tmp_path):
    retriever = build_retriever(tmp_path)
    agent = KnowledgeRetrieverAgent(retriever)
    context = JobContext.create(user_request="Teach ggplot2").model_copy(
        update={
            "state": {
                "course_specification": {
                    "title": "ggplot2",
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
                }
            }
        }
    )
    result = agent.run(context)
    assert result.outputs["knowledge_assessment"]["sufficient"] is False
