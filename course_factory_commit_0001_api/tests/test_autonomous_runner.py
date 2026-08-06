from pathlib import Path

from course_factory import (
    Action,
    Agent,
    AgentDispatcher,
    AgentResult,
    AutonomousRunner,
    JobContext,
    JobStatus,
)

class StateAgent(Agent):
    name = "state_agent"
    capabilities = frozenset({"state"})

    def __init__(self, output_key: str, value):
        self.output_key = output_key
        self.value = value

    def run(self, context):
        return AgentResult.success(
            agent_name=self.name,
            outputs={self.output_key: self.value},
        )

def test_autonomous_runner_completes_all_required_actions(tmp_path):
    dispatcher = AgentDispatcher()

    dispatcher.register(
        Action.BUILD_INPUT,
        lambda: StateAgent(
            "course_specification",
            {
                "title": "R",
                "topic": "R",
                "audience": "Beginners",
                "duration_minutes": 60,
                "language": "English",
                "delivery_mode": "online",
                "level": "beginner",
                "prerequisites": [],
                "learning_objectives": [],
                "required_packages": [],
                "exercise_count": 0,
                "assumptions": [],
                "clarification_required": False,
                "clarification_question": None,
            },
        ),
    )
    dispatcher.register(
        Action.LOCAL_RETRIEVAL,
        lambda: StateAgent(
            "local_knowledge_results",
            [],
        ),
    )
    dispatcher.register(
        Action.FUSE_EVIDENCE,
        lambda: StateAgent(
            "fused_evidence",
            {"topics":[],"source_document_count":0,"unique_document_count":0,"duplicate_document_ids":[]},
        ),
    )
    dispatcher.register(
        Action.ASSESS_KNOWLEDGE,
        lambda: StateAgent(
            "knowledge_assessment",
            {"sufficient":True,"confidence":1.0,"covered_topics":[],"missing_topics":[],"suggested_queries":[],"explanation":"Knowledge is sufficient for this test."},
        ),
    )
    dispatcher.register(
        Action.ITERATIVE_RETRIEVAL,
        lambda: StateAgent(
            "iterative_retrieval_report",
            {
                "tasks": [],
                "results": [],
                "query_count": 0,
                "result_count": 0,
                "duplicate_count": 0,
            },
        ),
    )
    dispatcher.register(
        Action.COURSE_PLANNING,
        lambda: StateAgent("course_outline", {}),
    )
    dispatcher.register(
        Action.WORKFLOW_PLANNING,
        lambda: StateAgent("workflow_plan", {}),
    )
    dispatcher.register(
        Action.R_CODE_GENERATION,
        lambda: StateAgent("generated_r_scripts", []),
    )
    dispatcher.register(
        Action.SECURITY_VALIDATION,
        lambda: StateAgent(
            "security_report",
            {"approved_count": 0, "rejected_count": 0},
        ),
    )
    dispatcher.register(
        Action.R_EXECUTION,
        lambda: StateAgent(
            "execution_report",
            {
                "results": [],
                "successful_tasks": [],
                "failed_tasks": [],
                "artifact_count": 0,
            },
        ),
    )
    dispatcher.register(
        Action.SLIDE_GENERATION,
        lambda: StateAgent("slide_deck", {}),
    )
    dispatcher.register(
        Action.EXERCISE_GENERATION,
        lambda: StateAgent("exercise_set", {}),
    )
    dispatcher.register(
        Action.CONTENT_REVIEW,
        lambda: StateAgent(
            "content_review",
            {
                "passed": True,
                "score": 1.0,
                "slide_deck": {
                    "artifact_name":"slide_deck","passed":True,"score":1.0,
                    "issues":[],"recommendations":[]
                },
                "exercise_set": {
                    "artifact_name":"exercise_set","passed":True,"score":1.0,
                    "issues":[],"recommendations":[]
                },
            },
        ),
    )
    dispatcher.register(
        Action.CONTENT_REPAIR,
        lambda: StateAgent("content_repair_report", {"attempt":1}),
    )
    dispatcher.register(
        Action.POWERPOINT_BUILDING,
        lambda: StateAgent(
            "presentation_path",
            str(tmp_path / "course.pptx"),
        ),
    )

    report = AutonomousRunner(dispatcher=dispatcher).run(
        JobContext.create(user_request="Create an R course")
    )

    assert report.context.status is JobStatus.COMPLETED
    assert report.decisions[-1].action is Action.FINISHED
    assert report.context.state["presentation_path"].endswith("course.pptx")

def test_runner_blocks_when_agent_requests_clarification():
    class BlockingAgent(Agent):
        name = "blocking"
        capabilities = frozenset({"blocking"})

        def run(self, context):
            from datetime import datetime, timezone
            from course_factory import AgentStatus
            now = datetime.now(timezone.utc)
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.BLOCKED,
                outputs={},
                errors=("Need audience information.",),
                started_at=now,
                finished_at=now,
            )

    dispatcher = AgentDispatcher()
    dispatcher.register(Action.BUILD_INPUT, BlockingAgent)

    report = AutonomousRunner(dispatcher=dispatcher).run(
        JobContext.create(user_request="Create something")
    )

    assert report.context.status is JobStatus.BLOCKED
