import time

from course_factory import (
    CheckpointStore,
    ExecutionEvent,
    ExecutionEventBus,
    GraphDefinition,
    GraphDispatcher,
    GraphNode,
    JobContext,
    MetricRecord,
    MetricsRegistry,
    Observability,
    ResumableGraphExecutor,
    WorkflowGraph,
)


def test_event_bus_supports_specific_and_wildcard_handlers():
    bus = ExecutionEventBus()
    seen = []

    bus.subscribe("node.started", lambda event: seen.append(("specific", event.name)))
    bus.subscribe("*", lambda event: seen.append(("wildcard", event.name)))

    bus.publish(
        ExecutionEvent(
            name="node.started",
            source="a",
        )
    )

    assert seen == [
        ("specific", "node.started"),
        ("wildcard", "node.started"),
    ]


def test_metrics_registry_measures_and_summarizes():
    metrics = MetricsRegistry()

    with metrics.measure("step.duration", stage="test"):
        time.sleep(0.001)

    latest = metrics.latest("step.duration")
    summary = metrics.summary()["step.duration"]

    assert latest is not None
    assert latest.value > 0
    assert summary["count"] == 1
    assert summary["total"] > 0


def test_metrics_csv_export(tmp_path):
    metrics = MetricsRegistry()
    metrics.record(
        MetricRecord(
            name="cache.hit",
            value=1,
            unit="count",
            tags={"artifact": "slides"},
        )
    )

    path = metrics.export_csv(tmp_path / "metrics.csv")

    text = path.read_text(encoding="utf-8")
    assert "cache.hit" in text
    assert "slides" in text


def test_resumable_executor_emits_graph_and_node_events(tmp_path):
    dispatcher = GraphDispatcher()
    dispatcher.register(
        "ok",
        lambda context, dependencies: {"ok": True},
    )

    graph = WorkflowGraph(
        GraphDefinition(
            graph_id="observed",
            nodes=(GraphNode(node_id="ok", action="ok"),),
        )
    )

    observability = Observability()
    events = []
    observability.events.subscribe(
        "*",
        lambda event: events.append(event.name),
    )

    executor = ResumableGraphExecutor(
        dispatcher=dispatcher,
        checkpoint_store=CheckpointStore(tmp_path / "checkpoints"),
        observability=observability,
    )

    report = executor.execute(
        graph,
        JobContext.create(user_request="Observe"),
    )

    assert report.failed == ()
    assert events == [
        "graph.started",
        "node.started",
        "node.finished",
        "graph.finished",
    ]
    assert observability.metrics.latest("node.duration") is not None
    assert observability.metrics.summary()["events.total"]["count"] == 4
