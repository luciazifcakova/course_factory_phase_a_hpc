from __future__ import annotations

import json

from .course_outline import Lesson
from .workflow_plan import WorkflowTask

R_CODE_SCHEMA = '''{
  "code": "complete executable R script",
  "expected_outputs": ["concrete relative files actually created"],
  "knowledge_ids": ["preserve supplied IDs only"]
}'''

SYSTEM_PROMPT = (
    "You are a senior R developer creating reproducible teaching examples. "
    "Return one complete executable R script that runs non-interactively with Rscript. "
    "Do not install packages, access the network, change working directory, invoke shell "
    "commands, or delete files. Use only approved packages and relative paths. Create "
    "parent output directories with dir.create(..., recursive=TRUE, showWarnings=FALSE). "
    "Use set.seed(12345) when randomness is involved. Prefer built-in datasets such as "
    "iris or mtcars. A lesson may create multiple figures. Figure files may be PNG or PDF "
    "only; prefer PNG for slides and never generate SVG. Every figure MUST be explicitly "
    "saved under figures/ using ggsave(), png()/dev.off(), or pdf()/dev.off(). Never rely "
    "on R's implicit Rplots.pdf graphics device. Use real approved-package functions only; "
    "for logarithmic ggplot2 axes use scale_x_log10(), scale_y_log10(), or documented "
    "transforms, never coord_log10(). The workflow contracts in required_output_contracts "
    "are authoritative and cannot be changed by the model. Choose concrete filenames that "
    "satisfy those contracts and list them in expected_outputs for provenance. Never list "
    "scripts/*.R or the source script itself in expected_outputs. Return JSON only."
)

def build_r_code_prompt(*, lesson: Lesson, task: WorkflowTask, knowledge: list[dict], lesson_content: dict | None = None, required_outputs: tuple[str, ...] = ()):
    payload = {
        "lesson_plan": lesson.model_dump(mode="json"),
        "lesson_content": lesson_content or {},
        "workflow_task": task.model_dump(mode="json"),
        "required_output_contracts": list(required_outputs),
        "approved_knowledge": knowledge,
        "requirements": [
            "Use only packages listed in workflow_task.required_packages.",
            "Do not use install.packages, download.file, system, shell, setwd, unlink, or file.remove.",
            "Use only relative paths.",
            "Planner-owned output contracts are fixed and cannot be redefined.",
            "For a figures/* contract create at least one PNG or PDF under figures/.",
            "Multiple figures are allowed when they teach distinct concepts.",
            "List concrete generated files in expected_outputs, but never scripts/*.R.",
            "Every plot must be saved explicitly; do not allow implicit Rplots.pdf.",
            "Keep the example suitable for the stated lesson objectives.",
        ],
    }
    return SYSTEM_PROMPT, json.dumps(payload, indent=2), R_CODE_SCHEMA
