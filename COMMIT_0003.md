# Commit 0003

## Commit message

```text
feat(r): generate and security-validate lesson R scripts

- plan R, figure and slide tasks from the course outline
- include generated lesson content in R-code prompts
- require deterministic relative output paths
- generate one R script per planned lesson
- validate package usage, unsafe operations and output paths
- reject unknown evidence identifiers
- persist workflow and validation reports
- expose generated scripts as job artifacts
- add integrated R-generation tests
```

## New job outputs

```text
workspace/jobs/JOB_ID/
  workflow_plan.json
  r_code_generation_report.json
  security_report.json
  scripts/
    LESSON_ID.R
```

Successful CLI output reports:

```json
{"status":"completed","current_step":"r_scripts_complete"}
```
