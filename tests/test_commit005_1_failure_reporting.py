from course_factory import AgentResult
from course_factory.types import AgentStatus


def test_failed_agent_result_can_preserve_diagnostic_outputs():
    result = AgentResult.failed(
        agent_name="slide_planner",
        errors=("real validation error",),
        outputs={
            "slide_planning_attempts": [
                {
                    "lesson_id": "LES-001",
                    "attempt": 1,
                }
            ]
        },
        metrics={
            "slide_planner_attempts": 1,
        },
    )

    assert result.status is AgentStatus.FAILED
    assert result.errors == (
        "real validation error",
    )
    assert result.outputs[
        "slide_planning_attempts"
    ][0]["lesson_id"] == "LES-001"
    assert result.metrics[
        "slide_planner_attempts"
    ] == 1


def test_failed_agent_result_remains_backward_compatible():
    result = AgentResult.failed(
        agent_name="test_agent",
        errors=("boom",),
    )

    assert result.status is AgentStatus.FAILED
    assert result.outputs == {}
    assert result.metrics == {}
