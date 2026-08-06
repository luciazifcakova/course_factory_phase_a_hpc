from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

from .document_models import ImportedDocument, QualityDecision, SourceType

class SourceQualityScorer:
    BASE_SCORES = {
        SourceType.OFFICIAL_DOC: 0.92,
        SourceType.CRAN: 0.95,
        SourceType.POSIT: 0.92,
        SourceType.R_PROJECT: 0.95,
        SourceType.BOOK: 0.80,
        SourceType.TUTORIAL: 0.72,
        SourceType.ARTICLE: 0.70,
        SourceType.LOCAL: 0.65,
        SourceType.BLOG: 0.45,
        SourceType.OTHER: 0.35,
    }

    def __init__(
        self,
        *,
        minimum_score: float = 0.65,
        minimum_characters: int = 300,
        preferred_domains: tuple[str, ...] = (
            "r-project.org",
            "cran.r-project.org",
            "posit.co",
            "tidyverse.org",
            "bioconductor.org",
        ),
        blocked_domains: tuple[str, ...] = (),
    ):
        self.minimum_score = minimum_score
        self.minimum_characters = minimum_characters
        self.preferred_domains = preferred_domains
        self.blocked_domains = blocked_domains

    def score(self, document: ImportedDocument) -> QualityDecision:
        reasons: list[str] = []
        score = self.BASE_SCORES[document.source_type]

        domain = ""
        if document.url:
            domain = urlparse(document.url).netloc.lower()
            if any(domain == d or domain.endswith("." + d) for d in self.blocked_domains):
                return QualityDecision(
                    accepted=False,
                    score=0.0,
                    reasons=("Blocked domain.",),
                )
            if any(domain == d or domain.endswith("." + d) for d in self.preferred_domains):
                score += 0.08
                reasons.append("Preferred domain.")

            if document.url.startswith("https://"):
                score += 0.02
                reasons.append("HTTPS source.")

        length = len(document.content)
        if length < self.minimum_characters:
            score -= 0.30
            reasons.append("Document is too short.")
        elif length > 2000:
            score += 0.03
            reasons.append("Substantial content length.")

        lower = document.content.lower()
        r_indicators = ("library(", "install.packages(", "function(", "ggplot(", "<-")
        indicator_count = sum(token in lower for token in r_indicators)
        score += min(0.05, indicator_count * 0.01)
        if indicator_count:
            reasons.append("Contains R-specific content.")

        spam_indicators = ("casino", "buy now", "click here", "sponsored content")
        if any(token in lower for token in spam_indicators):
            score -= 0.40
            reasons.append("Spam-like language detected.")

        score = min(1.0, max(0.0, score))
        accepted = score >= self.minimum_score
        if accepted:
            reasons.append("Accepted by quality threshold.")
        else:
            reasons.append("Rejected by quality threshold.")

        return QualityDecision(
            accepted=accepted,
            score=score,
            reasons=tuple(reasons),
        )
