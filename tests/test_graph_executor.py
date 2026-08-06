from course_factory import (
    GraphDefinition,
    GraphDispatcher,
    GraphExecutor,
    GraphNode,
    JobContext,
    NodeStatus,
    WorkflowGraph,
    build_course_generation_graph,
)


def test_workflow_graph_rejects_cycle():
    try:
        WorkflowGraph(
            GraphDefinition(
                graph_id="cycle",
                nodes=(
                    GraphNode(
                        node_id="a",
                        action="a",
                        depends_on=("b",),
                    ),
                    GraphNode(
                        node_id="b",
                        action="b",
                        depends_on=("a",),
                    ),
                ),
            )
        )
    except ValueError as exc:
        assert "cycle" in str(exc).lower()
    else:
        raise AssertionError("Expected cycle detection")


def test_graph_executor_runs_dependencies_and_parallel_branches():
    dispatcher = GraphDispatcher()
    dispatcher.register(
        "root",
        lambda context, dependencies: {"value": 2},
    )
    dispatcher.register(
        "double",
        lambda context, dependencies: {
            "value": dependencies["root"]["value"] * 2
        },
    )
    dispatcher.register(
        "triple",
        lambda context, dependencies: {
            "value": dependencies["root"]["value"] * 3
        },
    )
    dispatcher.register(
        "sum",
        lambda context, dependencies: {
            "value": (
                dependencies["double"]["value"]
                + dependencies["triple"]["value"]
            )
        },
    )

    graph = WorkflowGraph(
        GraphDefinition(
            graph_id="math",
            nodes=(
                GraphNode(node_id="root", action="root"),
                GraphNode(
                    node_id="double",
                    action="double",
                    depends_on=("root",),
                ),
                GraphNode(
                    node_id="triple",
                    action="triple",
                    depends_on=("root",),
                ),
                GraphNode(
                    node_id="sum",
                    action="sum",
                    depends_on=("double", "triple"),
                ),
            ),
        )
    )

    report = GraphExecutor(
        dispatcher=dispatcher,
        max_workers=2,
    ).execute(
        graph,
        JobContext.create(user_request="Run graph"),
    )

    assert report.failed == ()
    assert report.skipped == ()
    assert set(report.succeeded) == {
        "root", "double", "triple", "sum"
    }
    sum_record = next(
        record
        for record in report.records
        if record.node_id == "sum"
    )
    assert sum_record.outputs["value"] == 10


def test_graph_executor_retries_then_succeeds():
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
            graph_id="retry",
            nodes=(
                GraphNode(
                    node_id="flaky",
                    action="flaky",
                    max_retries=1,
                ),
            ),
        )
    )

    report = GraphExecutor(dispatcher=dispatcher).execute(
        graph,
        JobContext.create(user_request="Retry graph"),
    )

    assert report.failed == ()
    assert report.succeeded == ("flaky",)
    attempts = [
        record
        for record in report.records
        if record.node_id == "flaky"
    ]
    assert [record.status for record in attempts] == [
        NodeStatus.FAILED,
        NodeStatus.SUCCESS,
    ]


def test_graph_executor_skips_downstream_after_failure():
    dispatcher = GraphDispatcher()
    dispatcher.register(
        "fail",
        lambda context, dependencies: (_ for _ in ()).throw(
            RuntimeError("boom")
        ),
    )
    dispatcher.register(
        "child",
        lambda context, dependencies: {"unexpected": True},
    )

    graph = WorkflowGraph(
        GraphDefinition(
            graph_id="failure",
            nodes=(
                GraphNode(node_id="a", action="fail"),
                GraphNode(
                    node_id="b",
                    action="child",
                    depends_on=("a",),
                ),
            ),
        )
    )

    report = GraphExecutor(dispatcher=dispatcher).execute(
        graph,
        JobContext.create(user_request="Fail graph"),
    )

    assert report.failed == ("a",)
    assert report.skipped == ("b",)


def test_course_graph_exports_mermaid():
    graph = build_course_generation_graph()
    mermaid = graph.to_mermaid()

    assert "graph TD" in mermaid
    assert "outline --> slides" in mermaid
    assert "review --> powerpoint" in mermaid
