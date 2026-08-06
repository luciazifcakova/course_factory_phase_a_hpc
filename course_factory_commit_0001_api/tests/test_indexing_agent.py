from course_factory import (
    DocumentIndexingAgent,
    EmbeddingBackend,
    EmbeddingService,
    InMemoryVectorStore,
    JobContext,
    KnowledgeStore,
    LocalKnowledgeRetriever,
)

class FakeEmbeddingBackend(EmbeddingBackend):
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.5, 0.25]

def build_agent(tmp_path):
    retriever = LocalKnowledgeRetriever(
        metadata_store=KnowledgeStore(tmp_path / "knowledge.sqlite3"),
        vector_store=InMemoryVectorStore(),
        embeddings=EmbeddingService(FakeEmbeddingBackend()),
    )
    return DocumentIndexingAgent(retriever=retriever), retriever

def test_indexing_agent_indexes_chunks(tmp_path):
    doc = tmp_path / "tutorial.md"
    doc.write_text(
        "# ggplot2 tutorial\n\n"
        + ("Use library(ggplot2) and ggplot() to build plots. " * 80),
        encoding="utf-8",
    )
    agent, retriever = build_agent(tmp_path)
    context = JobContext.create(user_request="Index a tutorial").model_copy(
        update={
            "state": {
                "index_request": {
                    "path": str(doc),
                    "title": "ggplot2 tutorial",
                    "topic": "ggplot2",
                    "source_type": "official_doc",
                    "url": "https://ggplot2.tidyverse.org/",
                }
            }
        }
    )
    result = agent.run(context)
    report = result.outputs["index_report"]
    assert report["accepted"] is True
    assert report["chunks_indexed"] >= 2

    matches = retriever.retrieve("ggplot2 plots", topic="ggplot2", limit=5)
    assert matches
    assert matches[0].topic == "ggplot2"

def test_indexing_agent_rejects_low_quality_short_blog(tmp_path):
    doc = tmp_path / "bad.txt"
    doc.write_text("buy now casino", encoding="utf-8")
    agent, _ = build_agent(tmp_path)
    context = JobContext.create(user_request="Index source").model_copy(
        update={
            "state": {
                "index_request": {
                    "path": str(doc),
                    "title": "Bad source",
                    "topic": "R",
                    "source_type": "blog",
                }
            }
        }
    )
    result = agent.run(context)
    assert result.outputs["index_report"]["accepted"] is False
