from pathlib import Path

from course_factory import (
    DocumentChunker,
    HTMLImporter,
    MarkdownImporter,
    SourceQualityScorer,
    SourceType,
)

def test_markdown_importer(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text("# ggplot2\n\nUse `ggplot()` to create plots.", encoding="utf-8")
    doc = MarkdownImporter().import_document(
        path,
        title="ggplot2",
        topic="ggplot2",
        source_type=SourceType.OFFICIAL_DOC,
    )
    assert "ggplot()" in doc.content
    assert doc.topic == "ggplot2"

def test_html_importer_removes_navigation(tmp_path):
    path = tmp_path / "doc.html"
    path.write_text(
        "<html><head><title>T</title></head><body>"
        "<nav>menu</nav><main><h1>ggplot2</h1><p>Grammar of graphics.</p></main>"
        "</body></html>",
        encoding="utf-8",
    )
    doc = HTMLImporter().import_document(
        path,
        title="ggplot2",
        topic="ggplot2",
        source_type=SourceType.OFFICIAL_DOC,
    )
    assert "menu" not in doc.content
    assert "Grammar of graphics" in doc.content

def test_chunker_overlap_and_ids():
    text = ("A paragraph about ggplot2 themes. " * 80).strip()
    chunks = DocumentChunker(chunk_size=300, overlap=50).chunk(
        document_id="DOC-1",
        text=text,
    )
    assert len(chunks) > 1
    assert chunks[0].chunk_id == "DOC-1-0000"
    assert chunks[1].start_char < chunks[0].end_char

def test_quality_scorer_prefers_official_docs():
    from course_factory import ImportedDocument
    official = ImportedDocument(
        title="ggplot2 docs",
        source="web",
        source_type=SourceType.OFFICIAL_DOC,
        topic="ggplot2",
        content="library(ggplot2)\n" + ("documentation " * 100),
        url="https://ggplot2.tidyverse.org/",
    )
    score = SourceQualityScorer().score(official)
    assert score.accepted is True
    assert score.score >= 0.9
