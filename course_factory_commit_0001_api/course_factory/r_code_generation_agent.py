from pathlib import Path
from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .job_context import JobContext
from .llm_backend import LLMBackend
from .r_code_models import RCodeGenerationReport,RScriptArtifact
from .r_code_validator import RCodeValidator
from .r_prompt_builder import build_r_code_prompt
from .workflow_plan import TaskType,WorkflowPlan
class RCodeGenerationAgent(Agent):
    name='r_code_generator'; version='1.0.0'; capabilities=frozenset({'r_code_generation'})
    def __init__(self,backend:LLMBackend,*,output_dir='workspace/generated_r'):
        self.backend=backend; self.output_dir=Path(output_dir)
    def run(self,context:JobContext):
        outline_raw=context.state.get('course_outline'); plan_raw=context.state.get('workflow_plan')
        if not isinstance(outline_raw,dict) or not isinstance(plan_raw,dict):
            return AgentResult.failed(agent_name=self.name,errors=('course_outline or workflow_plan is missing',))
        try:
            outline=CourseOutline.model_validate(outline_raw); plan=WorkflowPlan.model_validate(plan_raw)
            lessons={lesson.lesson_id:lesson for module in outline.modules for lesson in module.lessons}
            knowledge=context.state.get('local_knowledge_results',[])
            scripts=[]; failed=[]; self.output_dir.mkdir(parents=True,exist_ok=True)
            for task in plan.tasks:
                if task.task_type is not TaskType.R_SCRIPT: continue
                lesson=lessons.get(task.lesson_id)
                if lesson is None: failed.append(task.task_id); continue
                system,user,schema=build_r_code_prompt(lesson=lesson,task=task,knowledge=knowledge if isinstance(knowledge,list) else [])
                response=self.backend.generate_json(system=system,user=user,schema_hint=schema)
                code=str(response['code']).strip(); expected=tuple(map(str,response.get('expected_outputs',[]))); ids=tuple(map(str,response.get('knowledge_ids',[])))
                validation=RCodeValidator(allowed_packages=task.required_packages).validate(code,expected)
                if not validation.ok: failed.append(task.task_id); continue
                target=self.output_dir/Path(task.output_artifacts[0]).name; target.write_text(code+'\n',encoding='utf-8')
                scripts.append(RScriptArtifact(task_id=task.task_id,lesson_id=task.lesson_id,relative_path=str(target),code=code,required_packages=task.required_packages,expected_outputs=expected,knowledge_ids=ids))
            report=RCodeGenerationReport(scripts=tuple(scripts),generated_count=len(scripts),failed_task_ids=tuple(failed))
            return AgentResult.success(agent_name=self.name,outputs={'r_code_generation_report':report.model_dump(mode='json'),'generated_r_scripts':[s.model_dump(mode='json') for s in report.scripts]},metrics={'generated_r_scripts':len(scripts),'failed_r_tasks':len(failed)})
        except Exception as exc:
            return AgentResult.failed(agent_name=self.name,errors=(f'{type(exc).__name__}: {exc}',))
