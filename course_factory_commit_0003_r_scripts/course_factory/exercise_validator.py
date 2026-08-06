from __future__ import annotations

from dataclasses import dataclass
import re

from .course_outline import CourseOutline
from .exercise_models import ExerciseSet, ExerciseType

@dataclass(frozen=True, slots=True)
class ExerciseValidationIssue:
    severity: str
    code: str
    message: str
    exercise_id: str | None = None

@dataclass(frozen=True, slots=True)
class ExerciseValidationResult:
    ok: bool
    issues: tuple[ExerciseValidationIssue, ...]

class ExerciseValidator:
    FORBIDDEN_R = (
        r"\bsystem\s*\(",
        r"\bshell\s*\(",
        r"\bdownload\.file\s*\(",
        r"\binstall\.packages\s*\(",
        r"\bunlink\s*\(",
    )

    def validate(
        self,
        *,
        outline: CourseOutline,
        exercise_set: ExerciseSet,
    ) -> ExerciseValidationResult:
        issues: list[ExerciseValidationIssue] = []
        lesson_ids = {
            lesson.lesson_id
            for module in outline.modules
            for lesson in module.lessons
        }

        for exercise in exercise_set.exercises:
            if exercise.lesson_id not in lesson_ids:
                issues.append(
                    ExerciseValidationIssue(
                        "error",
                        "unknown_lesson",
                        f"Exercise references unknown lesson {exercise.lesson_id!r}.",
                        exercise.exercise_id,
                    )
                )

            if exercise.exercise_type is ExerciseType.CODE and not exercise.starter_code:
                issues.append(
                    ExerciseValidationIssue(
                        "warning",
                        "missing_starter_code",
                        "Code exercise has no starter code.",
                        exercise.exercise_id,
                    )
                )

            if exercise.starter_code:
                for pattern in self.FORBIDDEN_R:
                    if re.search(pattern, exercise.starter_code):
                        issues.append(
                            ExerciseValidationIssue(
                                "error",
                                "unsafe_starter_code",
                                "Starter code contains a forbidden R operation.",
                                exercise.exercise_id,
                            )
                        )

            if exercise.estimated_minutes > 60 and exercise.difficulty == "beginner":
                issues.append(
                    ExerciseValidationIssue(
                        "warning",
                        "long_beginner_exercise",
                        "Beginner exercise is estimated to take more than 60 minutes.",
                        exercise.exercise_id,
                    )
                )

        return ExerciseValidationResult(
            ok=not any(issue.severity == "error" for issue in issues),
            issues=tuple(issues),
        )
