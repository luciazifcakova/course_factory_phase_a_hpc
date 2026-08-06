from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
import time

from .checkpoint_models import GraphCheckpoint
from .checkpoint_store import CheckpointStore
from .graph_dispatcher import GraphDispatcher
from .metrics_models import MetricRecord
from .graph_models import (
    GraphExecutionReport,
    NodeExecutionRecord,
    NodeStatus,
)
from .job_context import JobContext
from .workflow_graph import WorkflowGraph
from .execution_events import ExecutionEvent
from .observability import Observability


@dataclass(slots=True)
class ResumableGraphExecutor:
    dispatcher: GraphDispatcher
    checkpoint_store: CheckpointStore
    max_workers: int = 4
    observability: Observability | None = None

    def execute(
        self,
        graph: WorkflowGraph,
        context: JobContext,
        *,
        resume: bool = True,
        clear_checkpoint_on_success: bool = False,
    ) -> GraphExecutionReport:
        checkpoint = self._initial_checkpoint(
            graph,
            resume=resume,
        )

        if self.observability:
            self.observability.events.publish(
                ExecutionEvent(
                    name="graph.started",
                    source=graph.definition.graph_id,
                    payload={
                        "resume": resume,
                        "node_count": len(graph.nodes),
                    },
                )
            )

        completed = set(checkpoint.completed)
        failed = set(checkpoint.failed)
        skipped = set(checkpoint.skipped)
        attempts = dict(checkpoint.attempts)
        outputs = dict(checkpoint.outputs)
        records = list(checkpoint.records)
        running: set[str] = set()

        # Failed/skipped nodes are retried on resume unless their retry limit
        # was already exhausted.
        if resume:
            retryable_failed = {
                node_id
                for node_id in failed
                if attempts.get(node_id, 0)
                <= graph.nodes[node_id].max_retries
            }
            failed -= retryable_failed
            skipped = {
                node_id
                for node_id in skipped
                if not (
                    set(graph.all_upstream(node_id)) & retryable_failed
                )
            }

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
                            error=(
                                "Skipped because an upstream dependency "
                                "failed."
                            ),
                        )
                    )
                    self._save(
                        graph,
                        completed,
                        failed,
                        skipped,
                        attempts,
                        outputs,
                        records,
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
                    "Graph execution stalled; unresolved nodes: "
                    f"{unresolved}"
                )

            with ThreadPoolExecutor(
                max_workers=min(self.max_workers, len(ready))
            ) as pool:
                futures = {}

                for node in ready:
                    running.add(node.node_id)
                    attempts[node.node_id] = (
                        attempts.get(node.node_id, 0) + 1
                    )

                    dependency_outputs = {
                        parent: outputs[parent]
                        for parent in node.depends_on
                        if parent in outputs
                    }

                    if self.observability:
                        self.observability.events.publish(
                            ExecutionEvent(
                                name="node.started",
                                source=node.node_id,
                                payload={
                                    "action": node.action,
                                    "attempt": attempts[node.node_id],
                                },
                            )
                        )

                    future = pool.submit(
                        self._execute_node,
                        node.node_id,
                        graph,
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

                    if self.observability:
                        self.observability.metrics.record(
                            MetricRecord(
                                name="node.duration",
                                value=record.duration_seconds,
                                unit="seconds",
                                tags={
                                    "node_id": record.node_id,
                                    "action": record.action,
                                    "status": record.status.value,
                                },
                            )
                        )
                        self.observability.events.publish(
                            ExecutionEvent(
                                name="node.finished",
                                source=record.node_id,
                                payload={
                                    "action": record.action,
                                    "status": record.status.value,
                                    "attempt": record.attempt,
                                },
                            )
                        )

                    if record.status is NodeStatus.SUCCESS:
                        completed.add(node_id)
                        outputs[node_id] = record.outputs
                        failed.discard(node_id)
                        skipped.discard(node_id)
                    else:
                        node = graph.nodes[node_id]
                        if attempts[node_id] > node.max_retries:
                            failed.add(node_id)

                    self._save(
                        graph,
                        completed,
                        failed,
                        skipped,
                        attempts,
                        outputs,
                        records,
                    )

        report = GraphExecutionReport(
            graph_id=graph.definition.graph_id,
            records=tuple(records),
            succeeded=tuple(sorted(completed)),
            failed=tuple(sorted(failed)),
            skipped=tuple(sorted(skipped)),
        )

        if (
            clear_checkpoint_on_success
            and not report.failed
            and not report.skipped
        ):
            self.checkpoint_store.delete(graph.definition.graph_id)

        if self.observability:
            self.observability.events.publish(
                ExecutionEvent(
                    name="graph.finished",
                    source=graph.definition.graph_id,
                    payload={
                        "succeeded": len(report.succeeded),
                        "failed": len(report.failed),
                        "skipped": len(report.skipped),
                    },
                )
            )

        return report

    def _initial_checkpoint(
        self,
        graph: WorkflowGraph,
        *,
        resume: bool,
    ) -> GraphCheckpoint:
        if resume and self.checkpoint_store.exists(
            graph.definition.graph_id
        ):
            checkpoint = self.checkpoint_store.load(
                graph.definition.graph_id
            )
            if checkpoint.graph_id != graph.definition.graph_id:
                raise ValueError("Checkpoint graph_id mismatch")
            return checkpoint

        return GraphCheckpoint(
            graph_id=graph.definition.graph_id
        )

    def _save(
        self,
        graph: WorkflowGraph,
        completed: set[str],
        failed: set[str],
        skipped: set[str],
        attempts: dict[str, int],
        outputs: dict[str, dict],
        records: list[NodeExecutionRecord],
    ) -> None:
        self.checkpoint_store.save(
            GraphCheckpoint(
                graph_id=graph.definition.graph_id,
                completed=tuple(sorted(completed)),
                failed=tuple(sorted(failed)),
                skipped=tuple(sorted(skipped)),
                attempts=dict(sorted(attempts.items())),
                outputs=outputs,
                records=tuple(records),
            )
        )

    def _execute_node(
        self,
        node_id: str,
        graph: WorkflowGraph,
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
