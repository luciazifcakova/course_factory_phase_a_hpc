from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
import threading

from .execution_events import ExecutionEvent


EventHandler = Callable[[ExecutionEvent], None]


class ExecutionEventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []
        self._lock = threading.Lock()

    def subscribe(
        self,
        event_name: str,
        handler: EventHandler,
    ) -> None:
        with self._lock:
            if event_name == "*":
                self._wildcard_handlers.append(handler)
            else:
                self._handlers[event_name].append(handler)

    def publish(self, event: ExecutionEvent) -> None:
        with self._lock:
            handlers = tuple(self._handlers.get(event.name, ()))
            wildcard = tuple(self._wildcard_handlers)

        for handler in (*handlers, *wildcard):
            handler(event)
