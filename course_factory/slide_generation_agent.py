from __future__ import annotations

import json
from pathlib import Path

from .agent import Agent
from .agent_result import AgentResult
from .job_context import JobContext
from .lesson_content_models import (
    LessonContentSet,
)
from .llm_backend import (
    LLMBackend,
    StructuredOutputError,
    ensure_structured_backend,
)
from .slide_models import (
    CourseSlidePlan,
    LessonSlideDeck,
    LessonSlideText,
    Slide,
    SlideDeck,
    SlideGenerationAttempt,
    SlideGenerationReport,
)


class SlideGenerationAgent(Agent):
    name = "slide_generation"
    version = "1.0.0"
    capabilities = frozenset(
        {"slide_generation"}
    )

    def __init__(
        self,
        backend: LLMBackend,
        *,
        output_dir: str | Path,
        trace_dir: str | Path,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least one"
            )
        self.backend = ensure_structured_backend(
            backend
        )
        self.output_dir = Path(output_dir)
        self.trace_dir = Path(trace_dir)
        self.max_attempts = max_attempts

    @staticmethod
    def _write_json(
        path: Path,
        payload,
    ) -> None:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        path.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
                default=str,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are an expert R instructor writing concise teaching "
            "slides. Return data matching the supplied JSON schema. "
            "Write ONLY slide title, bullets, and speaker notes for the "
            "supplied fixed slide plan. Do not add, remove, reorder, or "
            "rename slide IDs. Use at most five short bullets per slide. "
            "Avoid paragraphs in bullets. Speaker notes may be more "
            "detailed and should help an instructor teach the concept. "
            "Use only facts supported by the supplied lesson content and "
            "R script excerpt; do not invent external claims. Do not "
            "invent artifact filenames because artifact references are "
            "merged later by deterministic code."
        )

    @staticmethod
    def _validate_text(
        *,
        text: LessonSlideText,
        plan,
    ) -> None:
        if text.lesson_id != plan.lesson_id:
            raise ValueError(
                "slide text returned wrong lesson_id"
            )

        expected_ids = [
            slide.slide_id
            for slide in plan.slides
        ]
        returned_ids = [
            slide.slide_id
            for slide in text.slides
        ]
        if returned_ids != expected_ids:
            raise ValueError(
                "slide text must preserve the exact "
                "planned slide IDs and order; expected="
                f"{expected_ids!r}, returned="
                f"{returned_ids!r}"
            )

    def run(
        self,
        context: JobContext,
    ) -> AgentResult:
        plan_raw = context.state.get(
            "slide_plan"
        )
        content_raw = context.state.get(
            "lesson_content"
        )
        scripts_raw = context.state.get(
            "approved_r_scripts",
            [],
        )

        if not isinstance(plan_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("slide_plan is missing",),
            )
        if not isinstance(content_raw, dict):
            return AgentResult.failed(
                agent_name=self.name,
                errors=("lesson_content is missing",),
            )

        try:
            course_plan = (
                CourseSlidePlan.model_validate(
                    plan_raw
                )
            )
            lesson_content = (
                LessonContentSet.model_validate(
                    content_raw
                )
            )
            content_by_id = {
                lesson.lesson_id: lesson
                for lesson
                in lesson_content.lessons
            }
            script_by_id = {
                item["lesson_id"]: item
                for item in scripts_raw
                if isinstance(item, dict)
            }

            lesson_decks = []
            attempts = []
            total_attempts = 0

            self.output_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            for plan in course_plan.lessons:
                source = content_by_id[
                    plan.lesson_id
                ]
                script = script_by_id.get(
                    plan.lesson_id,
                    {},
                )
                code = str(
                    script.get("code", "")
                )
                if len(code) > 8000:
                    code = (
                        code[:8000]
                        + "\n# ... truncated ..."
                    )

                system = self._system_prompt()
                original_user = (
                    "FIXED SLIDE PLAN:\n"
                    f"{plan.model_dump_json(indent=2)}\n\n"
                    "LESSON CONTENT:\n"
                    f"{source.model_dump_json(indent=2)}\n\n"
                    "R SCRIPT EXCERPT:\n"
                    f"{code}\n\n"
                    "Return exactly one SlideText entry "
                    "for every planned slide ID, in exactly "
                    "the same order."
                )
                user = original_user
                final_errors = ()

                for attempt in range(
                    1,
                    self.max_attempts + 1,
                ):
                    total_attempts += 1
                    trace = (
                        self.trace_dir
                        / plan.lesson_id
                    )
                    request_path = (
                        trace
                        / (
                            f"attempt_{attempt:02d}"
                            "_request.json"
                        )
                    )
                    response_path = (
                        trace
                        / (
                            f"attempt_{attempt:02d}"
                            "_response.json"
                        )
                    )
                    self._write_json(
                        request_path,
                        {
                            "system": system,
                            "user": user,
                            "json_schema": (
                                LessonSlideText
                                .model_json_schema()
                            ),
                        },
                    )

                    raw = {}
                    try:
                        generated = (
                            self.backend
                            .generate_structured(
                                LessonSlideText,
                                system=system,
                                user=user,
                            )
                        )
                        raw = generated.model_dump(
                            mode="json"
                        )
                        self._write_json(
                            response_path,
                            raw,
                        )
                        self._validate_text(
                            text=generated,
                            plan=plan,
                        )

                        text_by_id = {
                            item.slide_id: item
                            for item
                            in generated.slides
                        }

                        merged = []
                        for planned in plan.slides:
                            text_item = text_by_id[
                                planned.slide_id
                            ]
                            merged.append(
                                Slide(
                                    slide_id=(
                                        planned.slide_id
                                    ),
                                    lesson_id=(
                                        planned.lesson_id
                                    ),
                                    title=(
                                        text_item.title
                                    ),
                                    bullets=(
                                        text_item.bullets
                                    ),
                                    speaker_notes=(
                                        text_item
                                        .speaker_notes
                                    ),
                                    references=(
                                        source.source_ids
                                    ),
                                    code_artifact=(
                                        planned
                                        .code_artifact
                                    ),
                                    figure_artifact=(
                                        planned
                                        .figure_artifacts[0]
                                        if (
                                            planned
                                            .figure_artifacts
                                        )
                                        else None
                                    ),
                                    figure_artifacts=(
                                        planned
                                        .figure_artifacts
                                    ),
                                    layout=(
                                        planned.layout
                                    ),
                                )
                            )

                        deck = LessonSlideDeck(
                            lesson_id=plan.lesson_id,
                            lesson_title=(
                                plan.lesson_title
                            ),
                            slides=tuple(merged),
                        )
                        lesson_decks.append(deck)

                        lesson_path = (
                            self.output_dir
                            / f"{plan.lesson_id}.json"
                        )
                        self._write_json(
                            lesson_path,
                            deck.model_dump(
                                mode="json"
                            ),
                        )

                        attempts.append(
                            SlideGenerationAttempt(
                                agent=self.name,
                                lesson_id=(
                                    plan.lesson_id
                                ),
                                attempt=attempt,
                                succeeded=True,
                                request_path=str(
                                    request_path
                                ),
                                response_path=str(
                                    response_path
                                ),
                            )
                        )
                        break

                    except Exception as exc:
                        if isinstance(
                            exc,
                            StructuredOutputError,
                        ):
                            final_errors = (
                                str(exc),
                            )
                            if exc.raw_content:
                                try:
                                    raw = json.loads(
                                        exc.raw_content
                                    )
                                except Exception:
                                    raw = {
                                        "_raw_content": (
                                            exc.raw_content
                                        )
                                    }
                                self._write_json(
                                    response_path,
                                    raw,
                                )
                        else:
                            final_errors = (
                                f"{type(exc).__name__}: "
                                f"{exc}",
                            )

                        attempts.append(
                            SlideGenerationAttempt(
                                agent=self.name,
                                lesson_id=(
                                    plan.lesson_id
                                ),
                                attempt=attempt,
                                succeeded=False,
                                request_path=str(
                                    request_path
                                ),
                                response_path=(
                                    str(response_path)
                                    if response_path.exists()
                                    else None
                                ),
                                validation_errors=(
                                    final_errors
                                ),
                            )
                        )

                        if (
                            attempt
                            < self.max_attempts
                        ):
                            user = (
                                original_user
                                + "\n\nYour previous response "
                                "was invalid. Return the COMPLETE "
                                "corrected LessonSlideText. "
                                "Preserve every planned slide ID "
                                "and order exactly.\nERRORS:\n- "
                                + "\n- ".join(
                                    final_errors
                                )
                            )
                else:
                    raise ValueError(
                        f"slide content generation failed "
                        f"for {plan.lesson_id}: "
                        + "; ".join(final_errors)
                    )

            flat_slides = tuple(
                slide
                for lesson in lesson_decks
                for slide in lesson.slides
            )
            deck = SlideDeck(
                course_title=(
                    course_plan.course_title
                ),
                slides=flat_slides,
                lessons=tuple(
                    lesson_decks
                ),
            )

            report = SlideGenerationReport(
                lesson_count=len(
                    lesson_decks
                ),
                slide_count=len(
                    flat_slides
                ),
                slides_with_figures=sum(
                    bool(
                        slide.figure_artifacts
                    )
                    for slide in flat_slides
                ),
                slides_with_code=sum(
                    slide.code_artifact
                    is not None
                    for slide in flat_slides
                ),
                planner_attempts=0,
                content_attempts=(
                    total_attempts
                ),
                retries=(
                    total_attempts
                    - len(lesson_decks)
                ),
                attempts=tuple(attempts),
            )

        except Exception as exc:
            failure_outputs = {
                "slide_generation_attempts": [
                    item.model_dump(mode="json")
                    for item in (
                        attempts
                        if "attempts" in locals()
                        else []
                    )
                ]
            }
            self._write_json(
                self.trace_dir / "slide_generation_failure.json",
                {
                    "agent": self.name,
                    "error": (
                        f"{type(exc).__name__}: {exc}"
                    ),
                    **failure_outputs,
                },
            )
            return AgentResult.failed(
                agent_name=self.name,
                errors=(
                    f"{type(exc).__name__}: {exc}",
                ),
                outputs=failure_outputs,
            )

        return AgentResult.success(
            agent_name=self.name,
            outputs={
                "slide_deck": (
                    deck.model_dump(
                        mode="json"
                    )
                ),
                "slide_generation_report": (
                    report.model_dump(
                        mode="json"
                    )
                ),
            },
            metrics={
                "generated_slide_count": (
                    report.slide_count
                ),
                "generated_slide_lesson_count": (
                    report.lesson_count
                ),
                "slides_with_figures": (
                    report.slides_with_figures
                ),
                "slides_with_code": (
                    report.slides_with_code
                ),
                "slide_content_attempts": (
                    report.content_attempts
                ),
                "slide_content_retries": (
                    report.retries
                ),
            },
        )
