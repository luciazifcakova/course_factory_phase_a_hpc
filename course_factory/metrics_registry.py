from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import csv
import json
from pathlib import Path
import threading
import time

from .metrics_models import MetricRecord


class MetricsRegistry:
    def __init__(self) -> None:
        self._metrics: dict[str, list[MetricRecord]] = defaultdict(list)
        self._lock = threading.Lock()

    def record(self, metric: MetricRecord) -> None:
        with self._lock:
            self._metrics[metric.name].append(metric)

    def values(self, name: str) -> tuple[MetricRecord, ...]:
        with self._lock:
            return tuple(self._metrics.get(name, ()))

    def latest(self, name: str) -> MetricRecord | None:
        values = self.values(name)
        return values[-1] if values else None

    def all(self) -> tuple[MetricRecord, ...]:
        with self._lock:
            return tuple(
                record
                for name in sorted(self._metrics)
                for record in self._metrics[name]
            )

    def summary(self) -> dict[str, dict[str, float | int]]:
        output = {}
        with self._lock:
            for name, records in self._metrics.items():
                values = [record.value for record in records]
                output[name] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                    "total": sum(values),
                }
        return output

    @contextmanager
    def measure(
        self,
        metric_name: str,
        *,
        unit: str = "seconds",
        **tags: str,
    ):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.record(
                MetricRecord(
                    name=metric_name,
                    value=time.perf_counter() - started,
                    unit=unit,
                    tags=tags,
                )
            )

    def export_csv(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["name", "value", "unit", "timestamp", "tags"]
            )
            for record in self.all():
                writer.writerow(
                    [
                        record.name,
                        record.value,
                        record.unit,
                        record.timestamp.isoformat(),
                        json.dumps(record.tags, sort_keys=True),
                    ]
                )
        return target
