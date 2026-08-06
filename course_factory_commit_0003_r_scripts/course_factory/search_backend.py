from __future__ import annotations

from abc import ABC, abstractmethod
from hashlib import sha256
import requests

from .retrieval_models import RetrievalSource, RetrievalTask, SearchResult


class SearchBackend(ABC):
    @abstractmethod
    def search(self, task: RetrievalTask) -> tuple[SearchResult, ...]:
        raise NotImplementedError


class StaticSearchBackend(SearchBackend):
    """Deterministic backend used by tests and offline fixtures."""

    def __init__(self, results_by_query: dict[str, list[dict]]) -> None:
        self.results_by_query = results_by_query

    def search(self, task: RetrievalTask) -> tuple[SearchResult, ...]:
        raw_results = self.results_by_query.get(task.query, [])
        return tuple(
            SearchResult.model_validate(
                {
                    **item,
                    "query": task.query,
                    "source": task.source,
                    "topic": item.get("topic") or task.topic or task.query,
                }
            )
            for item in raw_results[: task.limit]
        )


class SearxNGBackend(SearchBackend):
    """
    Search a user-controlled SearxNG instance.

    This backend retrieves result snippets only. Full-page fetching and
    parsing are deliberately kept in a separate component.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search(self, task: RetrievalTask) -> tuple[SearchResult, ...]:
        response = requests.get(
            f"{self.base_url}/search",
            params={
                "q": task.query,
                "format": "json",
                "language": "en",
                "safesearch": 1,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()

        results: list[SearchResult] = []
        for item in payload.get("results", [])[: task.limit]:
            url = str(item.get("url") or "")
            title = str(item.get("title") or url or task.query)
            content = str(item.get("content") or title)
            digest = sha256(
                f"{task.query}\0{url}\0{title}".encode("utf-8")
            ).hexdigest()[:16]

            results.append(
                SearchResult(
                    result_id=f"web-{digest}",
                    query=task.query,
                    title=title,
                    url=url or None,
                    source=RetrievalSource.WEB,
                    source_type="search_result",
                    topic=task.topic or task.query,
                    content=content,
                    quality_score=0.40,
                    metadata={
                        "engine": str(item.get("engine") or ""),
                    },
                )
            )

        return tuple(results)
