from enum import StrEnum
from .exceptions import InvalidStateTransitionError
from .workflow_state import WorkflowState, StageStatus

class WorkflowStage(StrEnum):
    INITIALIZED="initialized"; PREFLIGHT="preflight"; INPUT_BUILDING="input_building"
    LOCAL_RETRIEVAL="local_retrieval"; KNOWLEDGE_ROUTING="knowledge_routing"
    WEB_RESEARCH="web_research"; COURSE_PLANNING="course_planning"
    WORKFLOW_BUILDING="workflow_building"; CODE_GENERATION="code_generation"
    CODE_REVIEW="code_review"; SECURITY_VALIDATION="security_validation"
    EXECUTION="execution"; OUTPUT_VALIDATION="output_validation"
    POWERPOINT_BUILDING="powerpoint_building"; COMPLETED="completed"; FAILED="failed"

TRANSITIONS={
 WorkflowStage.INITIALIZED:frozenset({WorkflowStage.PREFLIGHT,WorkflowStage.INPUT_BUILDING,WorkflowStage.FAILED}),
 WorkflowStage.PREFLIGHT:frozenset({WorkflowStage.INPUT_BUILDING,WorkflowStage.FAILED}),
 WorkflowStage.INPUT_BUILDING:frozenset({WorkflowStage.LOCAL_RETRIEVAL,WorkflowStage.COURSE_PLANNING,WorkflowStage.COMPLETED,WorkflowStage.FAILED}),
 WorkflowStage.LOCAL_RETRIEVAL:frozenset({WorkflowStage.KNOWLEDGE_ROUTING,WorkflowStage.FAILED}),
 WorkflowStage.KNOWLEDGE_ROUTING:frozenset({WorkflowStage.WEB_RESEARCH,WorkflowStage.COURSE_PLANNING,WorkflowStage.FAILED}),
 WorkflowStage.WEB_RESEARCH:frozenset({WorkflowStage.COURSE_PLANNING,WorkflowStage.FAILED}),
 WorkflowStage.COURSE_PLANNING:frozenset({WorkflowStage.WORKFLOW_BUILDING,WorkflowStage.COMPLETED,WorkflowStage.FAILED}),
 WorkflowStage.WORKFLOW_BUILDING:frozenset({WorkflowStage.CODE_GENERATION,WorkflowStage.FAILED}),
 WorkflowStage.CODE_GENERATION:frozenset({WorkflowStage.CODE_REVIEW,WorkflowStage.FAILED}),
 WorkflowStage.CODE_REVIEW:frozenset({WorkflowStage.SECURITY_VALIDATION,WorkflowStage.CODE_GENERATION,WorkflowStage.FAILED}),
 WorkflowStage.SECURITY_VALIDATION:frozenset({WorkflowStage.EXECUTION,WorkflowStage.CODE_GENERATION,WorkflowStage.FAILED}),
 WorkflowStage.EXECUTION:frozenset({WorkflowStage.OUTPUT_VALIDATION,WorkflowStage.FAILED}),
 WorkflowStage.OUTPUT_VALIDATION:frozenset({WorkflowStage.POWERPOINT_BUILDING,WorkflowStage.CODE_GENERATION,WorkflowStage.FAILED}),
 WorkflowStage.POWERPOINT_BUILDING:frozenset({WorkflowStage.COMPLETED,WorkflowStage.FAILED}),
 WorkflowStage.COMPLETED:frozenset(), WorkflowStage.FAILED:frozenset()
}

class StateMachine:
    def start(self,state):
        if state.current_stage is not None: raise InvalidStateTransitionError("already active")
        return state.start_stage(WorkflowStage.INITIALIZED.value)

    def transition(self,state,source,target,reason=""):
        if target not in TRANSITIONS[source]:
            raise InvalidStateTransitionError(f"{source}->{target} invalid")
        if source.value not in state.stages: raise InvalidStateTransitionError("source missing")
        rec=state.stages[source.value]
        if rec.status not in {StageStatus.RUNNING,StageStatus.SUCCESS}:
            raise InvalidStateTransitionError("source not active")
        updated=state if rec.status is StageStatus.SUCCESS else state.finish_stage(source.value,True,reason)
        if target is WorkflowStage.FAILED:
            return updated.start_stage(target.value).finish_stage(target.value,False,reason)
        if target is WorkflowStage.COMPLETED:
            return updated.start_stage(target.value).finish_stage(target.value,True,reason)
        return updated.start_stage(target.value)
