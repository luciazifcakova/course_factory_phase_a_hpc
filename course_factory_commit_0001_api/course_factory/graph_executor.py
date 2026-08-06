from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
import time

from .graph_dispatcher import GraphDispatcher
from .graph_models import (
    GraphExecutionReport,
    NodeExecutionRecord,
    NodeStatus,
)
from .job_context import JobContext
from .workflow_graph import WorkflowGraph


@dataclass(slots=True)
class GraphExecutor:
    dispatcher: GraphDispatcher
    max_workers: int = 4

    def execute(
        self,
        graph: WorkflowGraph,
        context: JobContext,
    ) -> GraphExecutionReport:
        completed: set[str] = set()
        failed: set[str] = set()
        skipped: set[str] = set()
        running: set[str] = set()
        attempts: dict[str, int] = {}
        outputs: dict[str, dict] = {}
        records: list[NodeExecutionRecord] = []

        while True:
            blocked = graph.blocked_by_failure(failed, completed)
            for node_id in blocked:
                if node_id not in skipped:
                    skipped.add(node_id)
                    node = graph.nodes[node_id]
                    records.append(
                        NodeExecutionRecord(
                            node_id=node_id,
                            action=node.action,
                            status=NodeStatus.SKIPPED,
                            attempt=attempts.get(node_id, 0),
                            error="Skipped because an upstream dependency failed.",
                        )
                    )

            ready = tuple(
                node
                for node in graph.ready_nodes(
                    completed=completed,
                    running=running,
                    failed=failed | skipped,
                )
                if node.node_id not in skipped
            )

            if not ready:
                terminal = completed | failed | skipped
                if len(terminal) == len(graph.nodes):
                    break
                unresolved = sorted(set(graph.nodes) - terminal)
                raise RuntimeError(
                    f"Graph execution stalled; unresolved nodes: {unresolved}"
                )

            with ThreadPoolExecutor(
                max_workers=min(self.max_workers, len(ready))
            ) as pool:
                futures = {}
                for node in ready:
                    running.add(node.node_id)
                    attempts[node.node_id] = attempts.get(node.node_id, 0) + 1

                    dependency_outputs = {
                        parent: outputs[parent]
                        for parent in node.depends_on
                        if parent in outputs
                    }
                    future = pool.submit(
                        self._execute_node,
                        graph,
                        node.node_id,
                        context,
                        dependency_outputs,
                        attempts[node.node_id],
                    )
                    futures[future] = node.node_id

                for future in as_completed(futures):
                    node_id = futures[future]
                    running.discard(node_id)
                    record = future.result()
                    records.append(record)

                    if record.status is NodeStatus.SUCCESS:
                        completed.add(node_id)
                        outputs[node_id] = record.outputs
                        continue

                    node = graph.nodes[node_id]
                    if attempts[node_id] <= node.max_retries:
                        continue

                    failed.add(node_id)

        return GraphExecutionReport(
            graph_id=graph.definition.graph_id,
            records=tuple(records),
            succeeded=tuple(sorted(completed)),
            failed=tuple(sorted(failed)),
            skipped=tuple(sorted(skipped)),
        )

    def _execute_node(
        self,
        graph: WorkflowGraph,
        node_id: str,
        context: JobContext,
        dependency_outputs: dict,
        attempt: int,
    ) -> NodeExecutionRecord:
        node = graph.nodes[node_id]
        started = time.perf_counter()
        try:
            outputs = self.dispatcher.execute(
                node.action,
                context,
                dependency_outputs,
            )
            return NodeExecutionRecord(
                node_id=node.node_id,
                action=node.action,
                status=NodeStatus.SUCCESS,
                attempt=attempt,
                outputs=outputs,
                duration_seconds=time.perf_counter() - started,
            )
        except Exception as exc:
            return NodeExecutionRecord(
                node_id=node.node_id,
                action=node.action,
                status=NodeStatus.FAILED,
                attempt=attempt,
                error=f"{type(exc).__name__}: {exc}",
                duration_seconds=time.perf_counter() - started,
            )
