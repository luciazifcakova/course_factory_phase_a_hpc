from __future__ import annotations

from pathlib import Path

from .agent_dispatcher import AgentDispatcher
from .autonomous_models import Action
from .autonomous_runner import AutonomousRunner
from .course_planner_agent import CoursePlannerAgent
from .exercise_generation_agent import ExerciseGenerationAgent
from .evidence_fusion_agent import EvidenceFusionAgent
from .knowledge_assessment_agent import KnowledgeAssessmentAgent
from .iterative_retrieval_agent import IterativeRetrievalAgent
from .search_backend import SearchBackend
from .execution_agent import ExecutionAgent
from .execution_models import ExecutionRuntime
from .input_builder_agent import InputBuilderAgent
from .knowledge_retriever_agent import KnowledgeRetrieverAgent
from .llm_backend import LLMBackend
from .powerpoint_builder_agent import PowerPointBuilderAgent
from .review_agent import ReviewAgent
from .repair_agent import RepairAgent
from .r_code_generation_agent import RCodeGenerationAgent
from .r_workflow_planner_agent import RWorkflowPlannerAgent
from .security_validator_agent import SecurityValidatorAgent
from .slide_content_agent import SlideContentAgent

def build_autonomous_runner(
    *,
    llm_backend: LLMBackend,
    knowledge_retriever: KnowledgeRetrieverAgent,
    workspace: str | Path,
    apptainer_image: str | Path | None = None,
    execution_runtime: ExecutionRuntime = ExecutionRuntime.APPTAINER,
    iterative_search_backend: SearchBackend | None = None,
) -> AutonomousRunner:
    workspace = Path(workspace)
    dispatcher = AgentDispatcher()

    dispatcher.register(
        Action.BUILD_INPUT,
        lambda: InputBuilderAgent(llm_backend),
    )
    dispatcher.register(
        Action.LOCAL_RETRIEVAL,
        lambda: knowledge_retriever,
    )
    dispatcher.register(
        Action.FUSE_EVIDENCE,
        lambda: EvidenceFusionAgent(llm_backend),
    )
    dispatcher.register(
        Action.ASSESS_KNOWLEDGE,
        lambda: KnowledgeAssessmentAgent(llm_backend),
    )
    if iterative_search_backend is not None:
        dispatcher.register(
            Action.ITERATIVE_RETRIEVAL,
            lambda: IterativeRetrievalAgent(
                backend=iterative_search_backend,
            ),
        )
    dispatcher.register(
        Action.COURSE_PLANNING,
        lambda: CoursePlannerAgent(llm_backend),
    )
    dispatcher.register(
        Action.WORKFLOW_PLANNING,
        RWorkflowPlannerAgent,
    )
    dispatcher.register(
        Action.R_CODE_GENERATION,
        lambda: RCodeGenerationAgent(
            llm_backend,
            output_dir=workspace / "generated_r",
        ),
    )
    dispatcher.register(
        Action.SECURITY_VALIDATION,
        SecurityValidatorAgent,
    )
    dispatcher.register(
        Action.R_EXECUTION,
        lambda: ExecutionAgent(
            workspace=workspace / "execution",
            runtime=execution_runtime,
            apptainer_image=apptainer_image,
        ),
    )
    dispatcher.register(
        Action.SLIDE_GENERATION,
        lambda: SlideContentAgent(llm_backend),
    )
    dispatcher.register(
        Action.EXERCISE_GENERATION,
        lambda: ExerciseGenerationAgent(llm_backend),
    )
    dispatcher.register(Action.CONTENT_REVIEW, ReviewAgent)
    dispatcher.register(
        Action.CONTENT_REPAIR,
        lambda: RepairAgent(llm_backend),
    )
    dispatcher.register(
        Action.POWERPOINT_BUILDING,
        lambda: PowerPointBuilderAgent(
            output_dir=workspace / "presentations",
            artifact_root=workspace,
        ),
    )

    return AutonomousRunner(dispatcher=dispatcher)
