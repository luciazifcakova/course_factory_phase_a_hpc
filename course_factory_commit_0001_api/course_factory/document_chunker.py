from __future__ import annotations

import hashlib
import re

from .document_models import DocumentChunk

class DocumentChunker:
    def __init__(self, *, chunk_size: int = 1200, overlap: int = 150):
        if chunk_size < 200:
            raise ValueError("chunk_size must be at least 200 characters")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be >= 0 and smaller than chunk_size")
        self.chunk_size = chunk_size
        self.overlap = overlap

    @staticmethod
    def _preferred_break(text: str, start: int, hard_end: int) -> int:
        if hard_end >= len(text):
            return len(text)

        window = text[start:hard_end]
        candidates = [
            window.rfind("\n\n"),
            window.rfind("\n"),
            window.rfind(". "),
            window.rfind("; "),
            window.rfind(", "),
            window.rfind(" "),
        ]
        best = max(candidates)
        if best < int(len(window) * 0.55):
            return hard_end
        return start + best + (2 if window[best:best+2] in {". ", "; ", ", "} else 1)

    def chunk(
        self,
        *,
        document_id: str,
        text: str,
        metadata: dict | None = None,
    ) -> list[DocumentChunk]:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        chunks: list[DocumentChunk] = []
        start = 0
        index = 0

        while start < len(normalized):
            hard_end = min(len(normalized), start + self.chunk_size)
            end = self._preferred_break(normalized, start, hard_end)
            piece = normalized[start:end].strip()
            if piece:
                digest = hashlib.sha256(piece.encode("utf-8")).hexdigest()
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document_id}-{index:04d}",
                        document_id=document_id,
                        chunk_index=index,
                        text=piece,
                        start_char=start,
                        end_char=end,
                        sha256=digest,
                        metadata=metadata or {},
                    )
                )
                index += 1

            if end >= len(normalized):
                break
            next_start = max(0, end - self.overlap)
            if next_start <= start:
                next_start = end
            start = next_start

        return chunks
