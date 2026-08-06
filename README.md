# Course Factory — Sprint 1.9 Part 1

Adds integrated observability:

- thread-safe event bus
- wildcard event subscriptions
- graph and node lifecycle events
- thread-safe metrics registry
- duration measurement context manager
- metric summaries
- CSV export
- automatic event counters
- DAG executor instrumentation
- unit and integration tests

The resumable executor now emits:

```text
graph.started
node.started
node.finished
graph.finished
```

and records per-node execution duration.

```bash
python -m pip install -e ".[dev]"
pytest
```
# course_factory_phase_a_hpc
