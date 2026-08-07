from pathlib import Path

from course_factory import (
    CourseExecutionService, CourseExecutor, CreateCourseRequest, HPCSettings,
    RScriptArtifact, RuntimeResult, WorkspaceManager,
)

class StaticRepairBackend:
    def __init__(self, response): self.response=response; self.calls=0
    def generate_json(self, **kwargs): self.calls += 1; return self.response

class ImplicitPdfThenPngRouter:
    def __init__(self): self.calls=0
    def execute(self, task):
        self.calls += 1
        output=Path(task.working_directory)/"output"
        if self.calls == 1:
            (output/"Rplots.pdf").write_bytes(b"implicit")
            return RuntimeResult(task_id=task.task_id, runtime=task.runtime, return_code=1, stdout="", stderr="implicit graphics device", submitted=True, completed=True)
        (output/"figures").mkdir(parents=True, exist_ok=True)
        (output/"figures"/"debug_example.png").write_bytes(b"png")
        return RuntimeResult(task_id=task.task_id, runtime=task.runtime, return_code=0, stdout="ok", stderr="", submitted=True, completed=True)

def cfg(tmp_path):
    image=tmp_path/"course-r.sif"; image.write_bytes(b"image")
    return HPCSettings(workspace=tmp_path/"workspace", apptainer_image=image, allowed_r_packages=("base","ggplot2"), slurm_partition="cpu", slurm_cpus=2, slurm_memory_gb=8, slurm_time_minutes=60, slurm_poll_seconds=1, slurm_wait_seconds=60, local_timeout_seconds=60, r_execution_repair_attempts=2)

def test_source_script_metadata_cannot_be_execution_contract(tmp_path):
    settings=cfg(tmp_path); workspace=WorkspaceManager(settings.workspace); workspace.initialize()
    source=tmp_path/"LES-006.R"; source.write_text('library(ggplot2)\nplot(mtcars$wt, mtcars$mpg)\n')
    script=RScriptArtifact(task_id="LES-006.r_code", lesson_id="LES-006", relative_path=str(source), code=source.read_text(), required_packages=("ggplot2",), expected_outputs=("scripts/LES-006.R","figures/example1.png","figures/example2.png"), output_contracts=("figures/*",), knowledge_ids=())
    backend=StaticRepairBackend({"code": 'library(ggplot2)\ndir.create("figures", recursive=TRUE, showWarnings=FALSE)\np <- ggplot(mtcars, aes(wt, mpg)) + geom_point()\nggsave("figures/debug_example.png", p)\n', "expected_outputs":["figures/debug_example.png"], "knowledge_ids":[]})
    report=CourseExecutionService(settings=settings, workspace=workspace, router=ImplicitPdfThenPngRouter(), backend=backend).execute(job_id="job-les006", scripts=(script,), request=CreateCourseRequest(prompt="Create course", executor=CourseExecutor.LOCAL))
    assert report.succeeded
    assert backend.calls == 1
    result=report.results[0]
    assert result.repair_count == 1
    assert "scripts/LES-006.R" not in result.expected_outputs_missing
    assert "figures/debug_example.png" in result.expected_outputs_found

def test_figures_contract_accepts_pdf(tmp_path):
    settings=cfg(tmp_path); workspace=WorkspaceManager(settings.workspace); workspace.initialize()
    source=tmp_path/"LES-001.R"; source.write_text('# placeholder\n')
    script=RScriptArtifact(task_id="LES-001.r_code", lesson_id="LES-001", relative_path=str(source), code="# placeholder", output_contracts=("figures/*",))
    class PdfRouter:
        def execute(self, task):
            output=Path(task.working_directory)/"output"; (output/"figures").mkdir(parents=True, exist_ok=True); (output/"figures"/"plot.pdf").write_bytes(b"pdf")
            return RuntimeResult(task_id=task.task_id, runtime=task.runtime, return_code=0, stdout="ok", stderr="", submitted=True, completed=True)
    report=CourseExecutionService(settings=settings, workspace=workspace, router=PdfRouter(), backend=None).execute(job_id="job-pdf", scripts=(script,), request=CreateCourseRequest(prompt="Create course", executor=CourseExecutor.LOCAL))
    assert report.succeeded
    assert "figures/plot.pdf" in report.results[0].expected_outputs_found

def test_generation_rejects_source_script_as_runtime_output():
    from course_factory.r_code_generation_agent import RCodeGenerationAgent
    try:
        RCodeGenerationAgent._validate_output_contracts(contracts=("figures/*",), concrete_outputs=("scripts/LES-006.R","figures/example.png"))
    except ValueError as exc:
        assert "source files" in str(exc)
    else:
        raise AssertionError("scripts/*.R should never validate as runtime output")
