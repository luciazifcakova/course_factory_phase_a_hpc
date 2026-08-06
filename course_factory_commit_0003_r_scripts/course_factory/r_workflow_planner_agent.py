from __future__ import annotations

from .agent import Agent
from .agent_result import AgentResult
from .course_outline import CourseOutline
from .job_context import JobContext
from .workflow_plan import TaskType, WorkflowPlan, WorkflowTask

class RWorkflowPlannerAgent(Agent):
    name = "r_workflow_planner"
    version = "1.0.0"
    capabilities = frozenset({"workflow_planning"})

    def run(self, context: JobContext) -> AgentResult:
        raw = context.state.get("course_outline")
        if not isinstance(raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("course_outline is missing",),
            )

        try:
            outline = CourseOutline.model_validate(raw)
            tasks: list[WorkflowTask] = []

            previous_lesson_task: str | None = None
            for module in outline.modules:
                for lesson in module.lessons:
                    code_task_id = f"{lesson.lesson_id}.r_code"
                    figure_task_id = f"{lesson.lesson_id}.figure"
                    slide_task_id = f"{lesson.lesson_id}.slides"

                    dependencies = (
                        (previous_lesson_task,) if previous_lesson_task else ()
                    )

                    tasks.append(
                        WorkflowTask(
                            task_id=code_task_id,
                            task_type=TaskType.R_SCRIPT,
                            lesson_id=lesson.lesson_id,
                            description=f"Generate executable R code for {lesson.title}",
                            output_artifacts=(f"scripts/{lesson.lesson_id}.R",),
                            depends_on=dependencies,
                            required_packages=lesson.required_packages,
                            estimated_minutes=max(1, lesson.duration_minutes // 6),
                        )
                    )

                    if lesson.practical or lesson.requires_live_demo:
                        tasks.append(
                            WorkflowTask(
                                task_id=figure_task_id,
                                task_type=TaskType.FIGURE,
                                lesson_id=lesson.lesson_id,
                                description=f"Generate visual output for {lesson.title}",
                                input_artifacts=(f"scripts/{lesson.lesson_id}.R",),
                                output_artifacts=(f"figures/{lesson.lesson_id}.png",),
                                depends_on=(code_task_id,),
                                required_packages=lesson.required_packages,
                                estimated_minutes=max(1, lesson.duration_minutes // 10),
                            )
                        )

                    slide_dependencies = [code_task_id]
                    if lesson.practical or lesson.requires_live_demo:
                        slide_dependencies.append(figure_task_id)

                    tasks.append(
                        WorkflowTask(
                            task_id=slide_task_id,
                            task_type=TaskType.SLIDE_CONTENT,
                            lesson_id=lesson.lesson_id,
                            description=f"Generate slides for {lesson.title}",
                            input_artifacts=(
                                f"scripts/{lesson.lesson_id}.R",
                                *(
                                    (f"figures/{lesson.lesson_id}.png",)
                                    if lesson.practical or lesson.requires_live_demo
                                    else ()
                                ),
                            ),
                            output_artifacts=(f"slides/{lesson.lesson_id}.json",),
                            depends_on=tuple(slide_dependencies),
                            required_packages=lesson.required_packages,
                            estimated_minutes=max(1, lesson.duration_minutes // 8),
                        )
                    )

                    previous_lesson_task = slide_task_id

            plan = WorkflowPlan(
                course_title=outline.title,
                tasks=tuple(tasks),
            )

        except Exception as exc:
            return AgentResult.failed(
                agent_name=self.name,
                errors=(f"{type(exc).__name__}: {exc}",),
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={"workflow_plan": plan.model_dump(mode="json")},
            metrics={
                "workflow_task_count": len(plan.tasks),
                "r_script_task_count": sum(
                    task.task_type is TaskType.R_SCRIPT for task in plan.tasks
                ),
                "figure_task_count": sum(
                    task.task_type is TaskType.FIGURE for task in plan.tasks
                ),
                "slide_task_count": sum(
                    task.task_type is TaskType.SLIDE_CONTENT for task in plan.tasks
                ),
            },
        )
