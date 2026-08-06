from pathlib import Path

from course_factory import (
    HPCSettings,
    SQLiteJobStore,
    WorkspaceManager,
    build_apptainer_r_task,
)
from course_factory.runtime_models import (
    ResourceRequest,
    RuntimeKind,
    RuntimeTask,
)
from course_factory.slurm_runtime import SlurmRuntimeBackend


def test_sqlite_job_store_round_trip(tmp_path):
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.create_job(
        job_id="job1",
        request={"topic": "R"},
    )
    store.update_job(
        job_id="job1",
        status="running",
        current_step="planning",
        patch={"value": 5},
    )
    store.add_event(
        job_id="job1",
        step="planning",
        message="Started.",
    )

    job = store.get_job("job1")
    events = store.list_events("job1")

    assert job["status"] == "running"
    assert job["state"]["value"] == 5
    assert events[0]["message"] == "Started."


def test_workspace_manager_isolates_tasks(tmp_path):
    manager = WorkspaceManager(tmp_path)
    manager.initialize()

    first = manager.task_directory(
        job_id="job1",
        task_id="lesson/one",
    )
    second = manager.task_directory(
        job_id="job1",
        task_id="lesson two",
    )

    assert first != second
    assert (first / "output").is_dir()
    assert (second / "logs").is_dir()


def test_apptainer_task_builder(tmp_path):
    image = tmp_path / "course-r.sif"
    image.write_bytes(b"image")

    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "script.R").write_text(
        "print('ok')",
        encoding="utf-8",
    )
    for name in ("output", "logs"):
        (task_dir / name).mkdir()

    task = build_apptainer_r_task(
        task_id="lesson",
        task_directory=task_dir,
        image=image,
        runtime=RuntimeKind.SLURM,
        resources=ResourceRequest(
            cpus=2,
            memory_gb=4,
            time_minutes=30,
            partition="cpu",
        ),
    )

    assert task.runtime is RuntimeKind.SLURM
    assert "apptainer" in task.command
    assert "--network" in task.command
    assert "none" in task.command
    assert "/job/script.R" in task.command


def test_slurm_script_uses_markers_not_sacct(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()

    task = RuntimeTask(
        task_id="r-task",
        command=("echo", "hello"),
        working_directory=str(tmp_path),
        runtime=RuntimeKind.SLURM,
        resources=ResourceRequest(
            cpus=2,
            memory_gb=8,
            time_minutes=60,
            partition="cpu",
        ),
        stdout_path=str(logs / "stdout.log"),
        stderr_path=str(logs / "stderr.log"),
    )

    backend = SlurmRuntimeBackend()
    _, exit_path, finished_path = backend._paths(task)
    script = backend._script_text(
        task,
        exit_path=exit_path,
        finished_path=finished_path,
    )

    assert "sacct" not in script
    assert str(exit_path) in script
    assert str(finished_path) in script
    assert "trap finish_course_factory_job EXIT" in script
    assert "#SBATCH --partition=cpu" in script


def test_settings_model_accepts_only_apptainer_slurm(tmp_path):
    settings = HPCSettings(
        workspace=tmp_path,
        apptainer_image=tmp_path / "image.sif",
        allowed_r_packages=("base",),
        slurm_partition="cpu",
        slurm_cpus=2,
        slurm_memory_gb=8,
        slurm_time_minutes=60,
        slurm_poll_seconds=5,
        slurm_wait_seconds=600,
        local_timeout_seconds=300,
    )

    assert settings.slurm_partition == "cpu"
    assert settings.allowed_r_packages == ("base",)
