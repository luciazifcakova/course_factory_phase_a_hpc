from __future__ import annotations

from collections.abc import Callable

from .job_context import JobContext
from .runtime_models import RuntimeTask
from .runtime_router import RuntimeRouter


DistributedAction = Callable[
    [JobContext, dict],
    RuntimeTask | dict,
]


class DistributedGraphDispatcher:
    def __init__(self, router: RuntimeRouter) -> None:
        self.router = router
        self._actions: dict[str, DistributedAction] = {}

    def register(
        self,
        action: str,
        handler: DistributedAction,
    ) -> None:
        if action in self._actions:
            raise ValueError(
                f"Action {action!r} is already registered"
            )
        self._actions[action] = handler

    def execute(
        self,
        action: str,
        context: JobContext,
        dependency_outputs: dict,
    ) -> dict:
        handler = self._actions.get(action)
        if handler is None:
            raise KeyError(
                f"No distributed handler registered for {action!r}"
            )

        prepared = handler(context, dependency_outputs)
        if isinstance(prepared, dict):
            return prepared
        if not isinstance(prepared, RuntimeTask):
            raise TypeError(
                "Distributed action handlers must return RuntimeTask or dict"
            )

        result = self.router.execute(prepared)
        if not result.succeeded:
            raise RuntimeError(
                f"Runtime task {prepared.task_id!r} failed: "
                f"{result.stderr or result.return_code}"
            )

        return {
            "runtime_result": result.model_dump(mode="json"),
        }
