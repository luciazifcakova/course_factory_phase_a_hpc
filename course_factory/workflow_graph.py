from __future__ import annotations

from collections import defaultdict, deque

from .graph_models import GraphDefinition, GraphNode


class WorkflowGraph:
    def __init__(self, definition: GraphDefinition) -> None:
        self.definition = definition
        self.nodes = {
            node.node_id: node
            for node in definition.nodes
        }
        self.parents: dict[str, set[str]] = defaultdict(set)
        self.children: dict[str, set[str]] = defaultdict(set)

        for node in definition.nodes:
            for parent in node.depends_on:
                self.parents[node.node_id].add(parent)
                self.children[parent].add(node.node_id)

        self._validate_acyclic()

    def _validate_acyclic(self) -> None:
        indegree = {
            node_id: len(self.parents.get(node_id, set()))
            for node_id in self.nodes
        }
        queue = deque(
            sorted(
                node_id
                for node_id, degree in indegree.items()
                if degree == 0
            )
        )
        visited = 0

        while queue:
            node_id = queue.popleft()
            visited += 1
            for child in sorted(self.children.get(node_id, set())):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)

        if visited != len(self.nodes):
            raise ValueError("Workflow graph contains a dependency cycle")

    def ready_nodes(
        self,
        completed: set[str],
        running: set[str],
        failed: set[str],
    ) -> tuple[GraphNode, ...]:
        ready = []
        for node_id, node in self.nodes.items():
            if node_id in completed or node_id in running or node_id in failed:
                continue
            parents = self.parents.get(node_id, set())
            if parents.issubset(completed):
                ready.append(node)
        return tuple(sorted(ready, key=lambda node: node.node_id))

    def blocked_by_failure(
        self,
        failed: set[str],
        completed: set[str],
    ) -> tuple[str, ...]:
        blocked = []
        for node_id in self.nodes:
            if node_id in failed or node_id in completed:
                continue
            upstream = self.all_upstream(node_id)
            if set(upstream) & failed:
                blocked.append(node_id)
        return tuple(sorted(blocked))

    def all_upstream(self, node_id: str) -> tuple[str, ...]:
        seen: set[str] = set()
        queue = deque([node_id])
        while queue:
            current = queue.popleft()
            for parent in sorted(self.parents.get(current, set())):
                if parent not in seen:
                    seen.add(parent)
                    queue.append(parent)
        return tuple(sorted(seen))

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for node in self.definition.nodes:
            label = node.action.replace('"', "'")
            lines.append(f'    {node.node_id}["{label}"]')
            for parent in node.depends_on:
                lines.append(f"    {parent} --> {node.node_id}")
        return "\n".join(lines)
