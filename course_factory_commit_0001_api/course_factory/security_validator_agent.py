from dataclasses import asdict
from .agent import Agent
from .agent_result import AgentResult
from .job_context import JobContext
from .r_code_models import RScriptArtifact
from .r_code_validator import RCodeValidator
class SecurityValidatorAgent(Agent):
    name='security_validator'; version='1.0.0'; capabilities=frozenset({'security_validation'})
    def run(self,context:JobContext):
        raw=context.state.get('generated_r_scripts')
        if not isinstance(raw,list):
            return AgentResult.failed(agent_name=self.name,errors=('generated_r_scripts is missing',))
        approved=[]; rejected=[]
        for item in raw:
            try:
                script=RScriptArtifact.model_validate(item)
                result=RCodeValidator(allowed_packages=script.required_packages).validate(script.code,script.expected_outputs)
                record={'task_id':script.task_id,'relative_path':script.relative_path,'issues':[asdict(i) for i in result.issues]}
                (approved if result.ok else rejected).append(record)
            except Exception as exc:
                rejected.append({'task_id':'unknown','issues':[{'severity':'error','rule':'invalid_script_record','message':str(exc),'line':None}]})
        return AgentResult.success(agent_name=self.name,outputs={'security_report':{'approved':approved,'rejected':rejected,'approved_count':len(approved),'rejected_count':len(rejected)},'approved_r_scripts':[item for item in raw if isinstance(item,dict) and any(a['task_id']==item.get('task_id') for a in approved)]},metrics={'security_approved_scripts':len(approved),'security_rejected_scripts':len(rejected)})
