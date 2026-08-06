from course_factory import *
class Demo(Agent):
    name="demo"; capabilities=frozenset({"input_builder"})
    def run(self,context): return AgentResult.success(agent_name=self.name,outputs={"ok":True})
r=CapabilityRegistry(); r.register(ExecutionPlan("input_builder",Demo,WorkflowStage.INPUT_BUILDING))
print(Supervisor(r).run(JobContext.create(user_request="demo"),["input_builder"]).context.model_dump_json(indent=2))
