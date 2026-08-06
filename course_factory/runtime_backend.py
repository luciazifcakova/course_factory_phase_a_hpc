from __future__ import annotations

from abc import ABC, abstractmethod

from .runtime_models import RuntimeResult, RuntimeTask


class RuntimeBackend(ABC):
    @abstractmethod
    def execute(self, task: RuntimeTask) -> RuntimeResult:
        raise NotImplementedError
