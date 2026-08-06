from __future__ import annotations

from pathlib import Path

from .exercise_models import ExerciseSet

class ExerciseMarkdownExporter:
    def export(
        self,
        exercise_set: ExerciseSet,
        output_dir: str | Path,
    ) -> tuple[Path, Path]:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exercises_path = output_dir / "Exercises.md"
        solutions_path = output_dir / "Solutions.md"

        exercise_lines = [f"# {exercise_set.course_title} — Exercises", ""]
        for index, exercise in enumerate(exercise_set.exercises, start=1):
            exercise_lines.extend(
                [
                    f"## Exercise {index}: {exercise.title}",
                    "",
                    f"**Lesson:** {exercise.lesson_id}",
                    f"**Type:** {exercise.exercise_type.value}",
                    f"**Estimated time:** {exercise.estimated_minutes} minutes",
                    "",
                    exercise.instructions,
                    "",
                ]
            )
            if exercise.starter_code:
                exercise_lines.extend(
                    ["```r", exercise.starter_code.rstrip(), "```", ""]
                )
            if exercise.hints:
                exercise_lines.append("### Hints")
                exercise_lines.extend(f"- {hint}" for hint in exercise.hints)
                exercise_lines.append("")

        solution_by_id = {
            solution.exercise_id: solution
            for solution in exercise_set.solutions
        }
        solution_lines = [f"# {exercise_set.course_title} — Solutions", ""]
        for index, exercise in enumerate(exercise_set.exercises, start=1):
            solution = solution_by_id.get(exercise.exercise_id)
            if not solution:
                continue
            solution_lines.extend(
                [
                    f"## Exercise {index}: {exercise.title}",
                    "",
                    solution.solution_text,
                    "",
                ]
            )
            if solution.solution_code:
                solution_lines.extend(
                    ["```r", solution.solution_code.rstrip(), "```", ""]
                )
            solution_lines.extend(
                ["### Explanation", "", solution.explanation, ""]
            )
            if solution.grading_points:
                solution_lines.append("### Grading points")
                solution_lines.extend(
                    f"- {point}" for point in solution.grading_points
                )
                solution_lines.append("")

        exercises_path.write_text("\n".join(exercise_lines), encoding="utf-8")
        solutions_path.write_text("\n".join(solution_lines), encoding="utf-8")
        return exercises_path, solutions_path
