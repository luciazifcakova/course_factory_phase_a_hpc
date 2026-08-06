from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from uuid import uuid4

import yaml

from .apptainer_tasks import build_apptainer_r_task
from .environment_preflight import run_environment_preflight
from .hpc_settings import settings
from .job_store import SQLiteJobStore
from .local_runtime import LocalRuntimeBackend
from .runtime_models import ResourceRequest, RuntimeKind
from .runtime_router import RuntimeRouter
from .slurm_runtime import SlurmRuntimeBackend
from .workspace_manager import WorkspaceManager


def _store() -> SQLiteJobStore:
    return SQLiteJobStore(
        settings.workspace / "state" / "jobs.sqlite3"
    )


def initialize_workspace() -> None:
    manager = WorkspaceManager(settings.workspace)
    manager.initialize()
    _store()
    print(settings.workspace)


def _parse_packages(value: str) -> tuple[str, ...]:
    return tuple(
        item.strip()
        for item in value.split(",")
        if item.strip()
    )


def command_preflight(args) -> int:
    initialize_workspace()
    result = run_environment_preflight(
        settings=settings,
        required_r_packages=_parse_packages(
            args.r_packages
        ),
        require_slurm=args.slurm,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


def command_status(args) -> int:
    print(
        json.dumps(
            _store().get_job(args.job_id),
            indent=2,
            default=str,
        )
    )
    return 0


def command_list(args) -> int:
    print(
        json.dumps(
            _store().list_jobs(limit=args.limit),
            indent=2,
        )
    )
    return 0


def command_events(args) -> int:
    print(
        json.dumps(
            _store().list_events(
                args.job_id,
                limit=args.limit,
            ),
            indent=2,
        )
    )
    return 0


def command_execute_r(args) -> int:
    initialize_workspace()

    if settings.apptainer_image is None:
        print(
            "APPTAINER_IMAGE is not configured.",
            file=sys.stderr,
        )
        return 2

    source_script = args.script.expanduser().resolve()
    if not source_script.is_file():
        print(
            f"R script does not exist: {source_script}",
            file=sys.stderr,
        )
        return 2

    job_id = args.job_id or f"job_{uuid4().hex}"
    task_id = args.task_id or source_script.stem
    manager = WorkspaceManager(settings.workspace)
    task_directory = manager.task_directory(
        job_id=job_id,
        task_id=task_id,
    )
    shutil.copy2(source_script, task_directory / "script.R")

    request = {
        "source_script": str(source_script),
        "executor": args.executor,
        "task_id": task_id,
    }
    store = _store()

    try:
        store.create_job(
            job_id=job_id,
            request=request,
        )
    except Exception:
        # Permit reuse of an explicitly supplied job ID.
        store.update_job(
            job_id=job_id,
            status="created",
            current_step="initialization",
            patch={"request": request},
        )

    store.add_event(
        job_id=job_id,
        step="execution",
        message="R execution submitted.",
        payload=request,
    )
    store.update_job(
        job_id=job_id,
        status="running",
        current_step="r_execution",
        patch={
            "task_directory": str(task_directory),
        },
    )

    runtime_kind = (
        RuntimeKind.SLURM
        if args.executor == "slurm"
        else RuntimeKind.LOCAL
    )

    task = build_apptainer_r_task(
        task_id=task_id,
        task_directory=task_directory,
        image=settings.apptainer_image,
        runtime=runtime_kind,
        resources=ResourceRequest(
            cpus=args.cpus or settings.slurm_cpus,
            memory_gb=(
                args.memory_gb
                or settings.slurm_memory_gb
            ),
            time_minutes=(
                args.time_minutes
                or settings.slurm_time_minutes
            ),
            partition=(
                args.partition
                or settings.slurm_partition
            ),
        ),
    )

    router = RuntimeRouter(
        local=LocalRuntimeBackend(),
        slurm=SlurmRuntimeBackend(
            poll_interval_seconds=(
                settings.slurm_poll_seconds
            ),
            wait_timeout_seconds=(
                settings.slurm_wait_seconds
            ),
        ),
    )

    result = router.execute(task)
    status = "completed" if result.succeeded else "failed"

    store.update_job(
        job_id=job_id,
        status=status,
        current_step="finished",
        patch={
            "runtime_result": result.model_dump(
                mode="json"
            ),
        },
    )
    store.add_event(
        job_id=job_id,
        step="execution",
        message=f"R execution {status}.",
        level="INFO" if result.succeeded else "ERROR",
        payload=result.model_dump(mode="json"),
    )

    print(
        json.dumps(
            {
                "job_id": job_id,
                "task_directory": str(task_directory),
                "result": result.model_dump(mode="json"),
            },
            indent=2,
            default=str,
        )
    )
    return 0 if result.succeeded else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="course-factory"
    )
    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    commands.add_parser(
        "init",
        help="Create the workspace and SQLite job database.",
    )

    preflight = commands.add_parser(
        "preflight",
        help="Validate Apptainer, R packages and optional SLURM.",
    )
    preflight.add_argument(
        "--r-packages",
        default="",
        help="Comma-separated R package list.",
    )
    preflight.add_argument(
        "--slurm",
        action="store_true",
        help="Require sbatch, squeue and scancel.",
    )

    execute_r = commands.add_parser(
        "execute-r",
        help="Run one R script through Apptainer locally or via SLURM.",
    )
    execute_r.add_argument("script", type=Path)
    execute_r.add_argument(
        "--executor",
        choices=("local", "slurm"),
        default="local",
    )
    execute_r.add_argument("--job-id")
    execute_r.add_argument("--task-id")
    execute_r.add_argument("--cpus", type=int)
    execute_r.add_argument("--memory-gb", type=int)
    execute_r.add_argument("--time-minutes", type=int)
    execute_r.add_argument("--partition")

    status = commands.add_parser("status")
    status.add_argument("job_id")

    jobs = commands.add_parser("list")
    jobs.add_argument("--limit", type=int, default=100)

    events = commands.add_parser("events")
    events.add_argument("job_id")
    events.add_argument("--limit", type=int, default=500)

    args = parser.parse_args()

    if args.command == "init":
        initialize_workspace()
        return
    if args.command == "preflight":
        raise SystemExit(command_preflight(args))
    if args.command == "execute-r":
        raise SystemExit(command_execute_r(args))
    if args.command == "status":
        raise SystemExit(command_status(args))
    if args.command == "list":
        raise SystemExit(command_list(args))
    if args.command == "events":
        raise SystemExit(command_events(args))


if __name__ == "__main__":
    main()
