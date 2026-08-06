from pathlib import Path
from course_factory import JobContext,RCodeGenerationAgent,RCodeValidator,SecurityValidatorAgent,StaticJSONBackend
OUTLINE={'title':'Intro ggplot2','audience':'Beginners','language':'English','modules':[{'module_id':'m1','title':'Basics','description':'','prerequisites':[],'lessons':[{'lesson_id':'scatter','title':'Scatter plots','duration_minutes':30,'objectives':['Create plot'],'practical':True,'requires_live_demo':True,'required_packages':['ggplot2'],'prerequisites':[],'knowledge_ids':['DOC-1']}]}],'learning_objectives':['Create plots'],'required_packages':['ggplot2'],'total_duration_minutes':60,'assumptions':[],'references':['DOC-1'],'version':'1.0'}
PLAN={'course_title':'Intro ggplot2','version':'1.0','tasks':[{'task_id':'scatter.r_code','task_type':'r_script','lesson_id':'scatter','description':'Generate R','input_artifacts':[],'output_artifacts':['scripts/scatter.R'],'depends_on':[],'required_packages':['ggplot2'],'estimated_minutes':5,'max_retries':2}]}
def test_validator_rejects_system():
    result=RCodeValidator(allowed_packages=('ggplot2',)).validate('library(ggplot2)\nsystem("rm -rf /")')
    assert not result.ok and any(i.rule=='system_call' for i in result.issues)
def test_generation(tmp_path):
    backend=StaticJSONBackend({'code':'library(ggplot2)\ndir.create("figures",showWarnings=FALSE)\np<-ggplot(iris,aes(Sepal.Length,Sepal.Width))+geom_point()\nggsave("figures/scatter.png",p)','expected_outputs':['figures/scatter.png'],'knowledge_ids':['DOC-1']})
    context=JobContext.create(user_request='Generate').model_copy(update={'state':{'course_outline':OUTLINE,'workflow_plan':PLAN,'local_knowledge_results':[{'document_id':'DOC-1'}]}})
    result=RCodeGenerationAgent(backend,output_dir=tmp_path).run(context)
    assert result.status.value=='success' and result.metrics['generated_r_scripts']==1
    assert Path(result.outputs['generated_r_scripts'][0]['relative_path']).exists()
def test_security_rejects_unsafe(tmp_path):
    script={'task_id':'bad','lesson_id':'bad','relative_path':str(tmp_path/'bad.R'),'code':'system("curl x")','required_packages':[],'expected_outputs':[],'knowledge_ids':[]}
    context=JobContext.create(user_request='Validate').model_copy(update={'state':{'generated_r_scripts':[script]}})
    result=SecurityValidatorAgent().run(context)
    assert result.outputs['security_report']['rejected_count']==1
