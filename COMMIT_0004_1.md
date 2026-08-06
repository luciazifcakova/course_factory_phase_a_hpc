# Commit 004.1

## Commit message

```text
fix(execution): add bounded LLM repair and re-execution loop

- inspect R exit codes, stderr and missing expected outputs
- send failed scripts and diagnostics back to the configured LLM
- require repaired scripts to use exact expected output paths
- validate repaired code before consuming another execution attempt
- rerun repaired scripts inside the same Apptainer/SLURM runtime
- reset task outputs between attempts to prevent stale-file success
- preserve repair requests, responses and corrected scripts
- add attempt history and repair metrics to execution_report.json
- keep repairs bounded through R_EXECUTION_REPAIR_ATTEMPTS
- add regression tests for wrong output directories and no-backend failure
```

## Configuration

```bash
R_EXECUTION_REPAIR_ATTEMPTS=2
```

## Repair traces

```text
workspace/jobs/JOB_ID/tasks/TASK_ID/
  repair/
    attempt_01/
      request.json
      response.json
    repaired_01.R
```

A script that writes `plots/LES-001.png` while the workflow requires
`figures/LES-001.png` is now repaired and executed again automatically.
