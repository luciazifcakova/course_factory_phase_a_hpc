from __future__ import annotations

from hashlib import sha256
import re

from .retrieval_models import SearchResult


class DocumentDeduplicator:
    @staticmethod
    def _canonical_text(result: SearchResult) -> str:
        text = " ".join(
            [result.title, result.url or "", result.content]
        ).lower()
        return re.sub(r"\s+", " ", text).strip()

    def deduplicate(
        self,
        results: tuple[SearchResult, ...],
    ) -> tuple[tuple[SearchResult, ...], int]:
        seen: set[str] = set()
        unique: list[SearchResult] = []
        duplicate_count = 0

        for result in results:
            digest = sha256(
                self._canonical_text(result).encode("utf-8")
            ).hexdigest()
            if digest in seen:
                duplicate_count += 1
                continue
            seen.add(digest)
            unique.append(result)

        return tuple(unique), duplicate_count
