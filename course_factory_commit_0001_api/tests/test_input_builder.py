from course_factory import (
    CapabilityRegistry,
    ExecutionPlan,
    InputBuilderAgent,
    JobContext,
    JobStatus,
    StaticJSONBackend,
    Supervisor,
    WorkflowStage,
)

VALID = {
    "title": "Introduction to ggplot2 for Microbiologists",
    "topic": "ggplot2",
    "audience": "Microbiologists with beginner R knowledge",
    "duration_minutes": 180,
    "language": "English",
    "delivery_mode": "online",
    "level": "beginner",
    "prerequisites": ["Basic R syntax"],
    "learning_objectives": [
        "Explain the grammar of graphics",
        "Create scatter plots",
    ],
    "required_packages": ["ggplot2"],
    "exercise_count": 4,
    "assumptions": [],
    "clarification_required": False,
    "clarification_question": None,
}

def test_input_builder_agent_success():
    agent = InputBuilderAgent(StaticJSONBackend(VALID))
    result = agent.run(JobContext.create(user_request="Teach ggplot2"))
    assert result.outputs["course_specification"]["topic"] == "ggplot2"
    assert result.metrics["exercise_count"] == 4

def test_input_builder_supervisor_integration():
    registry = CapabilityRegistry()
    registry.register(
        ExecutionPlan(
            capability="input_builder",
            factory=lambda: InputBuilderAgent(StaticJSONBackend(VALID)),
            stage=WorkflowStage.INPUT_BUILDING,
            max_retries=3,
            required_model="qwen3:14b",
        )
    )
    result = Supervisor(registry).run(
        JobContext.create(user_request="Create a ggplot2 course"),
        ["input_builder"],
    )
    assert result.context.status is JobStatus.COMPLETED
    assert result.context.state["course_specification"]["title"].startswith("Introduction")

def test_input_builder_retries_invalid_payload():
    invalid = {"title": "x"}
    agent = InputBuilderAgent(StaticJSONBackend(invalid))
    result = agent.run(JobContext.create(user_request="Teach R"))
    assert result.status.value == "retry"
    assert result.errors
