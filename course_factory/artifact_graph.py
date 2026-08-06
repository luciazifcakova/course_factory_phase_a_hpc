from __future__ import annotations

from collections import defaultdict, deque


class ArtifactGraph:
    def __init__(self) -> None:
        self._parents: dict[str, set[str]] = defaultdict(set)
        self._children: dict[str, set[str]] = defaultdict(set)
        self._nodes: set[str] = set()

    def add_artifact(self, artifact_id: str) -> None:
        if not artifact_id:
            raise ValueError("artifact_id cannot be empty")
        self._nodes.add(artifact_id)

    def add_dependency(self, parent: str, child: str) -> None:
        if parent == child:
            raise ValueError("artifact cannot depend on itself")
        self._nodes.update({parent, child})
        self._children[parent].add(child)
        self._parents[child].add(parent)

    def dependencies(self, artifact_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._parents.get(artifact_id, set())))

    def dependents(self, artifact_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._children.get(artifact_id, set())))

    def all_downstream(self, artifact_id: str) -> tuple[str, ...]:
        seen: set[str] = set()
        queue = deque([artifact_id])

        while queue:
            node = queue.popleft()
            for child in sorted(self._children.get(node, set())):
                if child not in seen:
                    seen.add(child)
                    queue.append(child)

        return tuple(sorted(seen))

    def all_upstream(self, artifact_id: str) -> tuple[str, ...]:
        seen: set[str] = set()
        queue = deque([artifact_id])

        while queue:
            node = queue.popleft()
            for parent in sorted(self._parents.get(node, set())):
                if parent not in seen:
                    seen.add(parent)
                    queue.append(parent)

        return tuple(sorted(seen))

    def contains(self, artifact_id: str) -> bool:
        return artifact_id in self._nodes
