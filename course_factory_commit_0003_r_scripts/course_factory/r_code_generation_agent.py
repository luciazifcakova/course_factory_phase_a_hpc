from __future__ import annotations

from pathlib import Path

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .job_context import JobContext
from .lesson_content_models import LessonContentSet
from .llm_backend import LLMBackend
from .r_code_models import RCodeGenerationReport, RScriptArtifact
from .r_code_validator import RCodeValidator
from .r_prompt_builder import build_r_code_prompt
from .workflow_plan import TaskType, WorkflowPlan


class RCodeGenerationAgent(Agent):
    name = "r_code_generator"
    version = "1.1.0"
    capabilities = frozenset({"r_code_generation"})

    def __init__(
        self,
        backend: LLMBackend,
        *,
        output_dir: str | Path = "workspace/generated_r",
    ) -> None:
        self.backend = backend
        self.output_dir = Path(output_dir)

    @staticmethod
    def _required_outputs(
        plan: WorkflowPlan,
        code_task_id: str,
    ) -> tuple[str, ...]:
        outputs: list[str] = []
        for task in plan.tasks:
            if code_task_id in task.depends_on and task.task_type in {
                TaskType.FIGURE,
                TaskType.TABLE,
            }:
                outputs.extend(task.output_artifacts)
        return tuple(dict.fromkeys(outputs))

    def run(self, context: JobContext) -> AgentResult:
        outline_raw = context.state.get("course_outline")
        plan_raw = context.state.get("workflow_plan")
        lesson_content_raw = context.state.get("lesson_content")

        if not isinstance(outline_raw, dict) or not isinstance(plan_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_outline or workflow_plan is missing",),
            )

        try:
            outline = CourseOutline.model_validate(outline_raw)
            plan = WorkflowPlan.model_validate(plan_raw)
            lesson_content = (
                LessonContentSet.model_validate(lesson_content_raw)
                if isinstance(lesson_content_raw, dict)
                else None
            )

            lessons = {
                lesson.lesson_id: lesson
                for module in outline.modules
                for lesson in module.lessons
            }
            content_by_lesson = {
                lesson.lesson_id: lesson.model_dump(mode="json")
                for lesson in (lesson_content.lessons if lesson_content else ())
            }
            knowledge = context.state.get("local_knowledge_results", [])
            knowledge_list = knowledge if isinstance(knowledge, list) else []

            scripts: list[RScriptArtifact] = []
            failed: list[str] = []
            failure_reasons: dict[str, list[str]] = {}
            self.output_dir.mkdir(parents=True, exist_ok=True)

            for task in plan.tasks:
                if task.task_type is not TaskType.R_SCRIPT:
                    continue

                lesson = lessons.get(task.lesson_id)
                if lesson is None:
                    failed.append(task.task_id)
                    failure_reasons[task.task_id] = ["Unknown lesson_id"]
                    continue

                required_outputs = self._required_outputs(
                    plan,
                    task.task_id,
                )
                system, user, schema = build_r_code_prompt(
                    lesson=lesson,
                    task=task,
                    knowledge=knowledge_list,
                    lesson_content=content_by_lesson.get(task.lesson_id),
                    required_outputs=required_outputs,
                )
                response = self.backend.generate_json(
                    system=system,
                    user=user,
                    schema_hint=schema,
                )

                code = str(response["code"]).strip()
                returned_outputs = tuple(
                    map(str, response.get("expected_outputs", []))
                )
                knowledge_ids = tuple(
                    map(str, response.get("knowledge_ids", []))
                )

                expected_outputs = required_outputs or returned_outputs
                if required_outputs and set(returned_outputs) != set(required_outputs):
                    failed.append(task.task_id)
                    failure_reasons[task.task_id] = [
                        "LLM expected_outputs did not exactly match required outputs",
                        f"required={list(required_outputs)!r}",
                        f"returned={list(returned_outputs)!r}",
                    ]
                    continue

                allowed_knowledge_ids = set(lesson.knowledge_ids)
                unknown_ids = set(knowledge_ids) - allowed_knowledge_ids
                if unknown_ids:
                    failed.append(task.task_id)
                    failure_reasons[task.task_id] = [
                        "Unknown knowledge IDs: " + ", ".join(sorted(unknown_ids))
                    ]
                    continue

                validation = RCodeValidator(
                    allowed_packages=task.required_packages
                ).validate(code, expected_outputs)
                if not validation.ok:
                    failed.append(task.task_id)
                    failure_reasons[task.task_id] = [
                        f"{issue.rule}: {issue.message}"
                        for issue in validation.issues
                    ]
                    continue

                target = self.output_dir / f"{task.lesson_id}.R"
                target.write_text(code.rstrip() + "\n", encoding="utf-8")
                scripts.append(
                    RScriptArtifact(
                        task_id=task.task_id,
                        lesson_id=task.lesson_id,
                        relative_path=str(target),
                        code=code,
                        required_packages=task.required_packages,
                        expected_outputs=expected_outputs,
                        knowledge_ids=knowledge_ids,
                    )
                )

            report = RCodeGenerationReport(
                scripts=tuple(scripts),
                generated_count=len(scripts),
                failed_task_ids=tuple(failed),
            )
            return AgentResult.success(
                agent_name=self.name,
                outputs={
                    "r_code_generation_report": {
                        **report.model_dump(mode="json"),
                        "failure_reasons": failure_reasons,
                    },
                    "generated_r_scripts": [
                        script.model_dump(mode="json")
                        for script in report.scripts
                    ],
                },
                metrics={
                    "generated_r_scripts": len(scripts),
                    "failed_r_tasks": len(failed),
                },
            )
        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )
