from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in os.getenv(name, default).split(",")
        if item.strip()
    )


@dataclass(frozen=True, slots=True)
class HPCSettings:
    workspace: Path
    apptainer_image: Path | None
    allowed_r_packages: tuple[str, ...]
    slurm_partition: str
    slurm_cpus: int
    slurm_memory_gb: int
    slurm_time_minutes: int
    slurm_poll_seconds: float
    slurm_wait_seconds: float
    local_timeout_seconds: int
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:14b"
    ollama_timeout_seconds: int = 900

    @classmethod
    def from_environment(cls) -> "HPCSettings":
        image_text = os.getenv("APPTAINER_IMAGE", "").strip()
        return cls(
            workspace=Path(
                os.getenv(
                    "COURSE_FACTORY_WORKSPACE",
                    "./workspace",
                )
            ).expanduser().resolve(),
            apptainer_image=(
                Path(image_text).expanduser().resolve()
                if image_text
                else None
            ),
            allowed_r_packages=_csv(
                "ALLOWED_R_PACKAGES",
                (
                    "base,stats,utils,datasets,graphics,grDevices,"
                    "methods,ggplot2,dplyr,tidyr,readr,stringr,"
                    "lubridate"
                ),
            ),
            slurm_partition=os.getenv(
                "SLURM_PARTITION",
                "cpu",
            ),
            slurm_cpus=int(
                os.getenv("SLURM_CPUS", "2")
            ),
            slurm_memory_gb=int(
                os.getenv("SLURM_MEMORY_GB", "8")
            ),
            slurm_time_minutes=int(
                os.getenv("SLURM_TIME_MINUTES", "60")
            ),
            slurm_poll_seconds=float(
                os.getenv("SLURM_POLL_SECONDS", "10")
            ),
            slurm_wait_seconds=float(
                os.getenv("SLURM_WAIT_SECONDS", "7200")
            ),
            local_timeout_seconds=int(
                os.getenv("LOCAL_TIMEOUT_SECONDS", "1800")
            ),
            ollama_base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://127.0.0.1:11434",
            ).rstrip("/"),
            ollama_model=os.getenv(
                "OLLAMA_MODEL",
                "qwen3:14b",
            ),
            ollama_timeout_seconds=int(
                os.getenv(
                    "OLLAMA_TIMEOUT_SECONDS",
                    "900",
                )
            ),
        )


settings = HPCSettings.from_environment()
