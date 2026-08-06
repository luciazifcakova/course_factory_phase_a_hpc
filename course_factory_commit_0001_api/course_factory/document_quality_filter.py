from __future__ import annotations

from urllib.parse import urlparse

from .retrieval_models import SearchResult


class DocumentQualityFilter:
    PREFERRED_DOMAINS = (
        "r-project.org",
        "cran.r-project.org",
        "posit.co",
        "tidyverse.org",
        "bioconductor.org",
    )

    def __init__(self, minimum_score: float = 0.45) -> None:
        self.minimum_score = minimum_score

    def score(self, result: SearchResult) -> SearchResult:
        score = result.quality_score
        domain = urlparse(result.url or "").netloc.lower()

        if any(
            domain == preferred or domain.endswith("." + preferred)
            for preferred in self.PREFERRED_DOMAINS
        ):
            score += 0.35

        lower = result.content.lower()
        if any(
            token in lower
            for token in (
                "library(",
                "ggplot(",
                "function(",
                "data.frame",
                "documentation",
            )
        ):
            score += 0.10

        if len(result.content) < 40:
            score -= 0.20

        score = min(1.0, max(0.0, score))
        return result.model_copy(update={"quality_score": score})

    def filter(
        self,
        results: tuple[SearchResult, ...],
    ) -> tuple[SearchResult, ...]:
        scored = tuple(self.score(result) for result in results)
        return tuple(
            result
            for result in scored
            if result.quality_score >= self.minimum_score
        )
