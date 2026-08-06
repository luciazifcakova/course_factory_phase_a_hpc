from __future__ import annotations

from .local_runtime import LocalRuntimeBackend
from .runtime_backend import RuntimeBackend
from .runtime_models import RuntimeKind, RuntimeResult, RuntimeTask
from .slurm_runtime import SlurmRuntimeBackend


class RuntimeRouter:
    def __init__(
        self,
        *,
        local: RuntimeBackend | None = None,
        slurm: RuntimeBackend | None = None,
    ) -> None:
        self.backends = {
            RuntimeKind.LOCAL: local or LocalRuntimeBackend(),
            RuntimeKind.SLURM: slurm or SlurmRuntimeBackend(),
        }

    def execute(self, task: RuntimeTask) -> RuntimeResult:
        backend = self.backends.get(task.runtime)
        if backend is None:
            raise ValueError(
                f"No runtime backend configured for {task.runtime.value}"
            )
        return backend.execute(task)
