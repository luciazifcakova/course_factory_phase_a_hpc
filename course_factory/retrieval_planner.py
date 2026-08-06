from __future__ import annotations

from hashlib import sha256

from .evidence_models import KnowledgeAssessment
from .retrieval_models import RetrievalSource, RetrievalTask


class RetrievalPlanner:
    """Convert missing topics and suggested queries into ordered tasks."""

    def build(
        self,
        assessment: KnowledgeAssessment,
        *,
        source: RetrievalSource,
        default_limit: int = 5,
    ) -> tuple[RetrievalTask, ...]:
        queries = list(dict.fromkeys(assessment.suggested_queries))
        tasks: list[RetrievalTask] = []

        for index, query in enumerate(queries):
            digest = sha256(
                f"{source.value}\0{query}".encode("utf-8")
            ).hexdigest()[:12]
            topic = (
                assessment.missing_topics[index]
                if index < len(assessment.missing_topics)
                else None
            )
            tasks.append(
                RetrievalTask(
                    task_id=f"retrieve-{digest}",
                    query=query,
                    source=source,
                    priority=100 + index,
                    topic=topic,
                    limit=default_limit,
                )
            )

        return tuple(sorted(tasks, key=lambda task: task.priority))
