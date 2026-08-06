from course_factory import *

class A(Agent):
    name="a"; capabilities=frozenset({"input_builder"})
    def run(self,context):
        return AgentResult.success(agent_name=self.name,outputs={"title":"R"})

class B(Agent):
    name="b"; capabilities=frozenset({"course_planning"})
    def run(self,context):
        assert context.state["title"]=="R"
        return AgentResult.success(agent_name=self.name,outputs={"slides":10})

class Retry(Agent):
    name="retry"; capabilities=frozenset({"retry_test"}); calls=0
    def run(self,context):
        type(self).calls+=1
        if type(self).calls<3:
            return AgentResult.retry(agent_name=self.name,errors=("x",),attempt=type(self).calls)
        return AgentResult.success(agent_name=self.name,outputs={"ok":True},attempt=3)

def test_pipeline():
    r=CapabilityRegistry()
    r.register(ExecutionPlan("input_builder",A,WorkflowStage.INPUT_BUILDING))
    r.register(ExecutionPlan("course_planning",B,WorkflowStage.COURSE_PLANNING))
    out=Supervisor(r).run(JobContext.create(user_request="Teach R"),
                          ["input_builder","course_planning"])
    assert out.context.status is JobStatus.COMPLETED
    assert out.context.state["slides"]==10

def test_retry():
    Retry.calls=0
    r=CapabilityRegistry()
    r.register(ExecutionPlan("retry_test",Retry,WorkflowStage.INPUT_BUILDING,max_retries=3))
    out=Supervisor(r).run(JobContext.create(user_request="Retry"),["retry_test"])
    assert out.context.state["ok"] is True
    assert out.context.retry_counts["retry_test"]==2

def test_events():
    r=CapabilityRegistry(); r.register(ExecutionPlan("input_builder",A,WorkflowStage.INPUT_BUILDING))
    s=Supervisor(r); s.run(JobContext.create(user_request="ok"),["input_builder"])
    assert s.event_bus.history()[0].name=="workflow.started"
