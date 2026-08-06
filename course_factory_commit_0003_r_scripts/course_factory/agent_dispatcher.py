from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .agent import Agent
from .autonomous_models import Action
from .exceptions import MissingCapabilityError

AgentFactory = Callable[[], Agent]

@dataclass(frozen=True, slots=True)
class DispatchRegistration:
    action: Action
    factory: AgentFactory

class AgentDispatcher:
    def __init__(self) -> None:
        self._factories: dict[Action, AgentFactory] = {}

    def register(self, action: Action, factory: AgentFactory) -> None:
        if action in self._factories:
            raise ValueError(f"Action {action.value!r} is already registered.")
        self._factories[action] = factory

    def replace(self, action: Action, factory: AgentFactory) -> None:
        self._factories[action] = factory

    def create(self, action: Action) -> Agent:
        factory = self._factories.get(action)
        if factory is None:
            raise MissingCapabilityError(action.value)
        return factory()

    def actions(self) -> tuple[Action, ...]:
        return tuple(sorted(self._factories, key=lambda action: action.value))
