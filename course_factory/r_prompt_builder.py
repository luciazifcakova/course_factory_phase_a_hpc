from __future__ import annotations

import json

from .course_outline import Lesson
from .workflow_plan import WorkflowTask


R_CODE_SCHEMA = '''{
  "code": "complete executable R script",
  "expected_outputs": [
    "concrete relative file path actually created by the script"
  ],
  "knowledge_ids": ["preserve supplied IDs only"]
}'''


SYSTEM_PROMPT = (
    "You are a senior R developer creating reproducible teaching "
    "examples. Return one complete executable R script. The script must "
    "run non-interactively with Rscript. Do not install packages, access "
    "the network, change the working directory, invoke shell commands, "
    "or delete files. Use only approved packages and relative paths. "
    "Create parent output directories with "
    "dir.create(..., recursive=TRUE, showWarnings=FALSE). "
    "Use set.seed(12345) when randomness is involved. Prefer "
    "deterministic datasets supplied with R, such as iris or mtcars, "
    "unless the lesson requires something else. A lesson may create "
    "multiple figures. The workflow may supply output patterns such as "
    "'figures/*.png'; each such pattern means create at least one "
    "matching concrete file. List every concrete file created for the "
    "workflow in expected_outputs. Do not copy glob patterns themselves "
    "into expected_outputs. Return JSON only."
)


def build_r_code_prompt(
    *,
    lesson: Lesson,
    task: WorkflowTask,
    knowledge: list[dict],
    lesson_content: dict | None = None,
    required_outputs: tuple[str, ...] = (),
):
    payload = {
        "lesson_plan": lesson.model_dump(mode="json"),
        "lesson_content": lesson_content or {},
        "workflow_task": task.model_dump(mode="json"),
        "required_output_contracts": list(required_outputs),
        "approved_knowledge": knowledge,
        "requirements": [
            (
                "Use only packages listed in "
                "workflow_task.required_packages."
            ),
            (
                "Do not use install.packages, download.file, system, "
                "shell, setwd, unlink, or file.remove."
            ),
            "Use only relative paths.",
            (
                "For every required output contract, create at least one "
                "concrete matching file."
            ),
            (
                "Multiple figures are allowed and encouraged when they "
                "teach distinct concepts."
            ),
            (
                "List every concrete generated workflow output in "
                "expected_outputs."
            ),
            (
                "Keep the example suitable for teaching the stated "
                "lesson objectives."
            ),
        ],
    }
    return (
        SYSTEM_PROMPT,
        json.dumps(payload, indent=2),
        R_CODE_SCHEMA,
    )
