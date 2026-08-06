from __future__ import annotations

from .graph_models import GraphDefinition, GraphNode
from .workflow_graph import WorkflowGraph


def build_course_generation_graph() -> WorkflowGraph:
    definition = GraphDefinition(
        graph_id="course-generation-v1",
        nodes=(
            GraphNode(
                node_id="slides",
                action="generate_slides",
                depends_on=("outline",),
                max_retries=1,
            ),
            GraphNode(
                node_id="r_code",
                action="generate_r_code",
                depends_on=("outline",),
                max_retries=1,
            ),
            GraphNode(
                node_id="exercises",
                action="generate_exercises",
                depends_on=("outline",),
                max_retries=1,
            ),
            GraphNode(
                node_id="figures",
                action="execute_r_code",
                depends_on=("r_code",),
                max_retries=1,
            ),
            GraphNode(
                node_id="review",
                action="review_content",
                depends_on=("slides", "exercises", "figures"),
            ),
            GraphNode(
                node_id="powerpoint",
                action="build_powerpoint",
                depends_on=("review",),
            ),
            GraphNode(
                node_id="outline",
                action="use_outline",
            ),
        ),
    )
    return WorkflowGraph(definition)
