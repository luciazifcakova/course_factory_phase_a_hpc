from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from .agent import Agent
from .agent_result import AgentResult
from .document_chunker import DocumentChunker
from .document_importer import importer_for_path
from .document_models import SourceType
from .job_context import JobContext
from .retriever import LocalKnowledgeRetriever
from .source_quality import SourceQualityScorer

class DocumentIndexingAgent(Agent):
    name = "document_indexer"
    version = "1.0.0"
    capabilities = frozenset({"document_indexing"})

    def __init__(
        self,
        *,
        retriever: LocalKnowledgeRetriever,
        quality_scorer: SourceQualityScorer | None = None,
        chunker: DocumentChunker | None = None,
    ):
        self.retriever = retriever
        self.quality_scorer = quality_scorer or SourceQualityScorer()
        self.chunker = chunker or DocumentChunker()

    def run(self, context: JobContext) -> AgentResult:
        request = context.state.get("index_request")
        if not isinstance(request, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("index_request is missing from JobContext.state",),
            )

        try:
            path = Path(str(request["path"]))
            importer = importer_for_path(path)
            source_type = SourceType(str(request.get("source_type", "local")))
            document = importer.import_document(
                path,
                title=str(request.get("title") or path.stem),
                topic=str(request["topic"]),
                source_type=source_type,
                url=request.get("url"),
                metadata=request.get("metadata") or {},
            )
            quality = self.quality_scorer.score(document)
            if not quality.accepted:
                return AgentResult.success(
                    agent_name=self.name,
                    outputs={
                        "index_report": {
                            "accepted": False,
                            "quality_score": quality.score,
                            "reasons": list(quality.reasons),
                            "documents_indexed": 0,
                            "chunks_indexed": 0,
                        }
                    },
                    metrics={
                        "documents_indexed": 0,
                        "chunks_indexed": 0,
                    },
                )

            document_id = str(request.get("document_id") or f"DOC-{uuid4().hex[:12]}")
            chunks = self.chunker.chunk(
                document_id=document_id,
                text=document.content,
                metadata={
                    "topic": document.topic,
                    "source_type": document.source_type.value,
                },
            )

            indexed = 0
            duplicates = 0
            for chunk in chunks:
                _, inserted = self.retriever.index_document(
                    document_id=chunk.chunk_id,
                    title=f"{document.title} [{chunk.chunk_index + 1}]",
                    source=document.source,
                    source_type=document.source_type.value,
                    topic=document.topic,
                    content=chunk.text,
                    url=document.url,
                    metadata={
                        **document.metadata,
                        "parent_document_id": document_id,
                        "chunk_index": chunk.chunk_index,
                        "chunk_sha256": chunk.sha256,
                        "author": document.author,
                        "license": document.license,
                    },
                    quality_score=quality.score,
                )
                if inserted:
                    indexed += 1
                else:
                    duplicates += 1

            return AgentResult.success(
                agent_name=self.name,
                outputs={
                    "index_report": {
                        "accepted": True,
                        "document_id": document_id,
                        "quality_score": quality.score,
                        "reasons": list(quality.reasons),
                        "documents_indexed": 1,
                        "chunks_indexed": indexed,
                        "duplicate_chunks": duplicates,
                    }
                },
                metrics={
                    "documents_indexed": 1,
                    "chunks_indexed": indexed,
                    "duplicate_chunks": duplicates,
                },
            )
        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )
