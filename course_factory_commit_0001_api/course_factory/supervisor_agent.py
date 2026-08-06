from __future__ import annotations

from .autonomous_models import Action, Decision
from .job_context import JobContext
from .types import JobStatus

class SupervisorAgent:
    def decide(self, context: JobContext) -> Decision:
        if context.status is JobStatus.BLOCKED:
            return Decision(
                action=Action.BLOCKED,
                reason="The job is waiting for user clarification.",
            )
        if context.status is JobStatus.FAILED:
            return Decision(
                action=Action.FAILED,
                reason="The job is already marked as failed.",
            )

        state = context.state

        if "course_specification" not in state:
            return Decision(
                action=Action.BUILD_INPUT,
                reason="A normalized course specification has not been created.",
            )

        if "local_knowledge_results" not in state:
            return Decision(
                action=Action.LOCAL_RETRIEVAL,
                reason="Local knowledge has not been retrieved.",
            )

        if "fused_evidence" not in state:
            return Decision(
                action=Action.FUSE_EVIDENCE,
                reason="Retrieved evidence has not been fused.",
            )

        assessment = state.get("knowledge_assessment")
        if not isinstance(assessment, dict):
            return Decision(
                action=Action.ASSESS_KNOWLEDGE,
                reason="Fused evidence has not been assessed.",
            )

        if assessment.get("sufficient") is False:
            retries = context.retry_counts.get(
                Action.ITERATIVE_RETRIEVAL.value,
                0,
            )
            report = state.get("iterative_retrieval_report")
            if not isinstance(report, dict):
                return Decision(
                    action=Action.ITERATIVE_RETRIEVAL,
                    reason=(
                        "Knowledge is insufficient; execute the suggested "
                        "retrieval queries."
                    ),
                    retry_target=Action.ITERATIVE_RETRIEVAL,
                )

            if retries < 3:
                return Decision(
                    action=Action.FUSE_EVIDENCE,
                    reason=(
                        "Additional evidence was retrieved; rerun evidence "
                        "fusion and sufficiency assessment."
                    ),
                )

            return Decision(
                action=Action.FAILED,
                reason=(
                    "Knowledge remained insufficient after three iterative "
                    "retrieval attempts."
                ),
            )

        if "course_outline" not in state:
            return Decision(
                action=Action.COURSE_PLANNING,
                reason="The course outline has not been generated.",
            )

        if "workflow_plan" not in state:
            return Decision(
                action=Action.WORKFLOW_PLANNING,
                reason="The executable workflow plan is missing.",
            )

        if "generated_r_scripts" not in state:
            return Decision(
                action=Action.R_CODE_GENERATION,
                reason="R scripts have not been generated.",
            )

        security = state.get("security_report")
        if not isinstance(security, dict):
            return Decision(
                action=Action.SECURITY_VALIDATION,
                reason="Generated R scripts have not been security validated.",
            )
        if int(security.get("rejected_count", 0)) > 0:
            retries = context.retry_counts.get(Action.R_CODE_GENERATION.value, 0)
            if retries < 3:
                return Decision(
                    action=Action.R_CODE_GENERATION,
                    reason="Security validation rejected one or more R scripts.",
                    retry_target=Action.R_CODE_GENERATION,
                )
            return Decision(
                action=Action.FAILED,
                reason="R code remained unsafe after three generation attempts.",
            )

        if "execution_report" not in state:
            return Decision(
                action=Action.R_EXECUTION,
                reason="Approved R scripts have not been executed.",
            )

        execution = state.get("execution_report")
        if isinstance(execution, dict) and execution.get("failed_tasks"):
            retries = context.retry_counts.get(Action.R_CODE_GENERATION.value, 0)
            if retries < 3:
                return Decision(
                    action=Action.R_CODE_GENERATION,
                    reason="One or more R scripts failed execution.",
                    retry_target=Action.R_CODE_GENERATION,
                )
            return Decision(
                action=Action.FAILED,
                reason="R scripts still fail after three repair attempts.",
            )

        if "slide_deck" not in state:
            return Decision(
                action=Action.SLIDE_GENERATION,
                reason="Slide content has not been generated.",
            )

        if "exercise_set" not in state:
            return Decision(
                action=Action.EXERCISE_GENERATION,
                reason="Exercises and solutions have not been generated.",
            )

        review = state.get("content_review")
        if not isinstance(review, dict):
            return Decision(
                action=Action.CONTENT_REVIEW,
                reason="Generated slides and exercises have not been reviewed.",
            )

        if review.get("passed") is False:
            repairs = context.retry_counts.get(Action.CONTENT_REPAIR.value, 0)
            if repairs < 3:
                return Decision(
                    action=Action.CONTENT_REPAIR,
                    reason="Generated content failed review.",
                    retry_target=Action.CONTENT_REPAIR,
                )
            return Decision(
                action=Action.FAILED,
                reason="Content still fails review after three repairs.",
            )

        if "presentation_path" not in state:
            return Decision(
                action=Action.POWERPOINT_BUILDING,
                reason="The PowerPoint presentation has not been built.",
            )

        return Decision(
            action=Action.FINISHED,
            reason="All required course artifacts are present.",
        )
