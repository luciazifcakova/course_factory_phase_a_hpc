from __future__ import annotations
from .review_models import ReviewIssue, ReviewReport, ReviewSeverity

class SlideDeckReviewer:
    def review(self, deck: dict) -> ReviewReport:
        issues = []
        slides = deck.get("slides", [])
        if not isinstance(slides, list) or not slides:
            issues.append(ReviewIssue(
                code="empty_slide_deck",
                severity=ReviewSeverity.ERROR,
                message="Slide deck contains no slides.",
                field="slides",
            ))
            slides = []

        for i, slide in enumerate(slides):
            if not str(slide.get("title", "")).strip():
                issues.append(ReviewIssue(
                    code="missing_title",
                    severity=ReviewSeverity.ERROR,
                    message=f"Slide {i+1} has no title.",
                    field=f"slides[{i}].title",
                ))
            bullets = slide.get("bullets", [])
            if not isinstance(bullets, list) or not bullets:
                issues.append(ReviewIssue(
                    code="missing_bullets",
                    severity=ReviewSeverity.ERROR,
                    message=f"Slide {i+1} has no bullet content.",
                    field=f"slides[{i}].bullets",
                ))
            if not slide.get("references"):
                issues.append(ReviewIssue(
                    code="missing_references",
                    severity=ReviewSeverity.WARNING,
                    message=f"Slide {i+1} has no references.",
                    field=f"slides[{i}].references",
                ))

        errors = sum(x.severity is ReviewSeverity.ERROR for x in issues)
        warnings = sum(x.severity is ReviewSeverity.WARNING for x in issues)
        score = max(0.0, 1.0 - 0.25*errors - 0.08*warnings)
        return ReviewReport(
            artifact_name="slide_deck",
            passed=errors == 0 and score >= 0.70,
            score=score,
            issues=tuple(issues),
            recommendations=tuple(x.message for x in issues),
        )

class ExerciseSetReviewer:
    def review(self, data: dict) -> ReviewReport:
        issues = []
        exercises = data.get("exercises", [])
        solutions = data.get("solutions", [])
        if not isinstance(exercises, list) or not exercises:
            issues.append(ReviewIssue(
                code="missing_exercises",
                severity=ReviewSeverity.ERROR,
                message="No exercises were generated.",
                field="exercises",
            ))
            exercises = []
        if not isinstance(solutions, list):
            solutions = []

        exercise_ids = {x.get("exercise_id") for x in exercises if x.get("exercise_id")}
        solution_ids = {x.get("exercise_id") for x in solutions if x.get("exercise_id")}
        for missing in sorted(exercise_ids - solution_ids):
            issues.append(ReviewIssue(
                code="exercise_without_solution",
                severity=ReviewSeverity.ERROR,
                message=f"Exercise {missing!r} has no matching solution.",
                field="solutions",
            ))

        errors = sum(x.severity is ReviewSeverity.ERROR for x in issues)
        score = max(0.0, 1.0 - 0.30*errors)
        return ReviewReport(
            artifact_name="exercise_set",
            passed=errors == 0,
            score=score,
            issues=tuple(issues),
            recommendations=tuple(x.message for x in issues),
        )
