from __future__ import annotations

from collections import defaultdict
from graphlib import CycleError, TopologicalSorter

class ModuleGraph:
    def __init__(self) -> None:
        self._edges: dict[str, set[str]] = defaultdict(set)
        self._nodes: set[str] = set()

    def add_module(self, module_id: str) -> None:
        if not module_id:
            raise ValueError("module_id cannot be empty")
        self._nodes.add(module_id)

    def depends_on(self, module_id: str, prerequisite_id: str) -> None:
        if module_id == prerequisite_id:
            raise ValueError("a module cannot depend on itself")
        self._nodes.update({module_id, prerequisite_id})
        self._edges[module_id].add(prerequisite_id)

    def prerequisites(self, module_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._edges.get(module_id, set())))

    def ordered_modules(self) -> tuple[str, ...]:
        graph = {
            node: set(self._edges.get(node, set()))
            for node in self._nodes
        }
        try:
            return tuple(TopologicalSorter(graph).static_order())
        except CycleError as exc:
            raise ValueError("module dependency graph contains a cycle") from exc

    def validate_known_dependencies(self) -> None:
        unknown = {
            dependency
            for dependencies in self._edges.values()
            for dependency in dependencies
            if dependency not in self._nodes
        }
        if unknown:
            raise ValueError(f"unknown prerequisites: {sorted(unknown)}")

    def __contains__(self, item: str) -> bool:
        return item in self._nodes

    def __len__(self) -> int:
        return len(self._nodes)
