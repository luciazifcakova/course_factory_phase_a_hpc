from __future__ import annotations

from collections.abc import Callable

from .job_context import JobContext


GraphAction = Callable[[JobContext, dict], dict]


class GraphDispatcher:
    def __init__(self) -> None:
        self._actions: dict[str, GraphAction] = {}

    def register(self, action: str, handler: GraphAction) -> None:
        if action in self._actions:
            raise ValueError(f"Action {action!r} is already registered")
        self._actions[action] = handler

    def replace(self, action: str, handler: GraphAction) -> None:
        self._actions[action] = handler

    def execute(
        self,
        action: str,
        context: JobContext,
        dependency_outputs: dict,
    ) -> dict:
        handler = self._actions.get(action)
        if handler is None:
            raise KeyError(f"No graph handler registered for {action!r}")
        result = handler(context, dependency_outputs)
        if not isinstance(result, dict):
            raise TypeError(
                f"Graph action {action!r} must return a dict"
            )
        return result
