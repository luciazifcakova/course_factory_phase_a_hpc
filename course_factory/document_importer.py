from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .document_models import ImportedDocument, SourceType

class DocumentImporter(ABC):
    @abstractmethod
    def import_document(
        self,
        source: str | Path,
        *,
        title: str,
        topic: str,
        source_type: SourceType,
        url: str | None = None,
        metadata: dict | None = None,
    ) -> ImportedDocument:
        raise NotImplementedError

class TextImporter(DocumentImporter):
    def import_document(
        self,
        source,
        *,
        title,
        topic,
        source_type,
        url=None,
        metadata=None,
    ) -> ImportedDocument:
        path = Path(source)
        content = path.read_text(encoding="utf-8")
        return ImportedDocument(
            title=title,
            source=str(path),
            source_type=source_type,
            topic=topic,
            content=content,
            url=url,
            metadata=metadata or {},
        )

class MarkdownImporter(TextImporter):
    pass

class HTMLImporter(DocumentImporter):
    REMOVE_TAGS = ("script", "style", "nav", "footer", "aside", "noscript")

    def import_document(
        self,
        source,
        *,
        title,
        topic,
        source_type,
        url=None,
        metadata=None,
    ) -> ImportedDocument:
        path = Path(source)
        html = path.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "html.parser")
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        main = soup.find("main") or soup.find("article") or soup.body or soup
        content = "\n".join(
            line.strip()
            for line in main.get_text("\n").splitlines()
            if line.strip()
        )
        inferred_title = title
        if not inferred_title and soup.title and soup.title.string:
            inferred_title = soup.title.string.strip()

        return ImportedDocument(
            title=inferred_title,
            source=str(path),
            source_type=source_type,
            topic=topic,
            content=content,
            url=url,
            metadata=metadata or {},
        )

def importer_for_path(path: str | Path) -> DocumentImporter:
    suffix = Path(path).suffix.lower()
    if suffix in {".md", ".markdown"}:
        return MarkdownImporter()
    if suffix in {".html", ".htm"}:
        return HTMLImporter()
    if suffix in {".txt", ".r", ".rmd", ".qmd"}:
        return TextImporter()
    raise ValueError(f"unsupported document type: {suffix or '<none>'}")
