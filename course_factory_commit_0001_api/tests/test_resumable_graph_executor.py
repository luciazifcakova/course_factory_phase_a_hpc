from course_factory import (
    CheckpointStore,
    GraphDefinition,
    GraphDispatcher,
    GraphNode,
    GraphRunManifest,
    JobContext,
    ResumableGraphExecutor,
    WorkflowGraph,
)


def test_checkpoint_store_round_trip(tmp_path):
    from course_factory import GraphCheckpoint

    store = CheckpointStore(tmp_path)
    checkpoint = GraphCheckpoint(
        graph_id="g1",
        completed=("a",),
        attempts={"a": 1},
        outputs={"a": {"value": 1}},
    )

    store.save(checkpoint)
    loaded = store.load("g1")

    assert loaded.completed == ("a",)
    assert loaded.outputs["a"]["value"] == 1


def test_resumable_executor_skips_already_completed_nodes(tmp_path):
    calls = {"a": 0, "b": 0}
    dispatcher = GraphDispatcher()

    def run_a(context, dependencies):
        calls["a"] += 1
        return {"value": 2}

    def run_b(context, dependencies):
        calls["b"] += 1
        return {"value": dependencies["a"]["value"] * 3}

    dispatcher.register("a", run_a)
    dispatcher.register("b", run_b)

    graph = WorkflowGraph(
        GraphDefinition(
            graph_id="resume-success",
            nodes=(
                GraphNode(node_id="a", action="a"),
                GraphNode(
                    node_id="b",
                    action="b",
                    depends_on=("a",),
                ),
            ),
        )
    )
    store = CheckpointStore(tmp_path / "checkpoints")
    executor = ResumableGraphExecutor(
        dispatcher=dispatcher,
        checkpoint_store=store,
    )

    first = executor.execute(
        graph,
        JobContext.create(user_request="First run"),
    )
    second = executor.execute(
        graph,
        JobContext.create(user_request="Second run"),
        resume=True,
    )

    assert first.failed == ()
    assert second.failed == ()
    assert calls == {"a": 1, "b": 1}


def test_resumable_executor_retries_failed_node_on_next_run(tmp_path):
    calls = {"count": 0}
    dispatcher = GraphDispatcher()

    def flaky(context, dependencies):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("temporary")
        return {"ok": True}

    dispatcher.register("flaky", flaky)

    graph = WorkflowGraph(
        GraphDefinition(
            graph_id="resume-failure",
            nodes=(
                GraphNode(
                    node_id="flaky",
                    action="flaky",
                    max_retries=1,
                ),
            ),
        )
    )
    store = CheckpointStore(tmp_path / "checkpoints")
    executor = ResumableGraphExecutor(
        dispatcher=dispatcher,
        checkpoint_store=store,
    )

    # First execution already retries within the same run and succeeds.
    report = executor.execute(
        graph,
        JobContext.create(user_request="Retry"),
    )

    assert report.failed == ()
    assert calls["count"] == 2
    assert store.exists("resume-failure")


def test_manifest_reports_pending_nodes(tmp_path):
    dispatcher = GraphDispatcher()
    graph = WorkflowGraph(
        GraphDefinition(
            graph_id="manifest",
            nodes=(
                GraphNode(node_id="a", action="a"),
                GraphNode(
                    node_id="b",
                    action="b",
                    depends_on=("a",),
                ),
            ),
        )
    )
    store = CheckpointStore(tmp_path / "checkpoints")
    manifest = GraphRunManifest(graph, store).render()

    assert manifest["pending"] == ["a", "b"]
    assert manifest["completed"] == []


def test_checkpoint_can_be_cleared_after_success(tmp_path):
    dispatcher = GraphDispatcher()
    dispatcher.register(
        "ok",
        lambda context, dependencies: {"ok": True},
    )
    graph = WorkflowGraph(
        GraphDefinition(
            graph_id="clear-after-success",
            nodes=(GraphNode(node_id="ok", action="ok"),),
        )
    )
    store = CheckpointStore(tmp_path / "checkpoints")
    executor = ResumableGraphExecutor(
        dispatcher=dispatcher,
        checkpoint_store=store,
    )

    report = executor.execute(
        graph,
        JobContext.create(user_request="Clear"),
        clear_checkpoint_on_success=True,
    )

    assert report.failed == ()
    assert not store.exists("clear-after-success")
