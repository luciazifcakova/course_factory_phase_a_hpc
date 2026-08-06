from pathlib import Path

from course_factory import (
    DistributedGraphDispatcher,
    JobContext,
    LocalRuntimeBackend,
    ResourceRequest,
    RuntimeKind,
    RuntimeResult,
    RuntimeRouter,
    RuntimeTask,
    SlurmRuntimeBackend,
)


def test_local_runtime_executes_command(tmp_path):
    task = RuntimeTask(
        task_id="hello",
        command=("python", "-c", "print('hello')"),
        working_directory=str(tmp_path),
        runtime=RuntimeKind.LOCAL,
    )

    result = LocalRuntimeBackend().execute(task)

    assert result.succeeded is True
    assert result.stdout.strip() == "hello"


def test_slurm_script_contains_requested_resources(tmp_path):
    backend = SlurmRuntimeBackend()
    task = RuntimeTask(
        task_id="r-job",
        command=("Rscript", "lesson.R"),
        working_directory=str(tmp_path),
        runtime=RuntimeKind.SLURM,
        resources=ResourceRequest(
            cpus=4,
            memory_gb=16,
            time_minutes=120,
            gpus=1,
            partition="gpu",
        ),
        stdout_path=str(tmp_path / "stdout.log"),
        stderr_path=str(tmp_path / "stderr.log"),
    )

    script = backend._script_text(task)

    assert "#SBATCH --cpus-per-task=4" in script
    assert "#SBATCH --mem=16G" in script
    assert "#SBATCH --time=120" in script
    assert "#SBATCH --gres=gpu:1" in script
    assert "#SBATCH --partition=gpu" in script
    assert "Rscript lesson.R" in script


class FakeRuntime:
    def execute(self, task):
        return RuntimeResult(
            task_id=task.task_id,
            runtime=task.runtime,
            return_code=0,
            stdout="done",
            stderr="",
            external_job_id="123",
            submitted=True,
            completed=True,
        )


def test_runtime_router_selects_slurm_backend(tmp_path):
    router = RuntimeRouter(
        local=FakeRuntime(),
        slurm=FakeRuntime(),
    )
    task = RuntimeTask(
        task_id="job",
        command=("echo", "x"),
        working_directory=str(tmp_path),
        runtime=RuntimeKind.SLURM,
    )

    result = router.execute(task)

    assert result.runtime is RuntimeKind.SLURM
    assert result.external_job_id == "123"


def test_distributed_dispatcher_executes_runtime_task(tmp_path):
    dispatcher = DistributedGraphDispatcher(
        RuntimeRouter(
            local=FakeRuntime(),
            slurm=FakeRuntime(),
        )
    )
    dispatcher.register(
        "run_r",
        lambda context, dependencies: RuntimeTask(
            task_id="run-r",
            command=("Rscript", "lesson.R"),
            working_directory=str(tmp_path),
            runtime=RuntimeKind.SLURM,
        ),
    )

    outputs = dispatcher.execute(
        "run_r",
        JobContext.create(user_request="Run R"),
        {},
    )

    assert outputs["runtime_result"]["external_job_id"] == "123"


def test_distributed_dispatcher_accepts_immediate_dict():
    dispatcher = DistributedGraphDispatcher(
        RuntimeRouter(
            local=FakeRuntime(),
            slurm=FakeRuntime(),
        )
    )
    dispatcher.register(
        "inline",
        lambda context, dependencies: {"value": 5},
    )

    outputs = dispatcher.execute(
        "inline",
        JobContext.create(user_request="Inline"),
        {},
    )

    assert outputs == {"value": 5}
