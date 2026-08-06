from __future__ import annotations

from dataclasses import dataclass, field

from .execution_event_bus import ExecutionEventBus
from .execution_events import ExecutionEvent
from .metrics_models import MetricRecord
from .metrics_registry import MetricsRegistry


@dataclass(slots=True)
class Observability:
    events: ExecutionEventBus = field(
        default_factory=ExecutionEventBus
    )
    metrics: MetricsRegistry = field(
        default_factory=MetricsRegistry
    )

    def __post_init__(self) -> None:
        self.events.subscribe("*", self._record_event_metric)

    def _record_event_metric(self, event: ExecutionEvent) -> None:
        self.metrics.record(
            MetricRecord(
                name="events.total",
                value=1.0,
                unit="count",
                tags={
                    "event": event.name,
                    "source": event.source,
                },
            )
        )
