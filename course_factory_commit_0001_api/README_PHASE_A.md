# Phase A — HPC operational integration

This update is based on Sprint 1.9 and ports the most useful
operational features from `course_factory_hpc_v2_1_2`.

## Added

- `.env`-based HPC settings
- `course-factory` CLI
- SQLite job and event database
- per-job/per-task isolated execution directories
- Apptainer-only R execution task builder
- environment and R-package preflight
- marker-based SLURM monitoring without `sacct`
- `squeue` disappearance detection
- supervisor timeout followed by `scancel`
- an executable R smoke test
- tests for Phase A components

## Install

```bash
git clone <your repository>
cd course_factory_sprint_1_9_part_1

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Copy and edit the environment file:

```bash
cp .env.example .env
```

At minimum set:

```bash
COURSE_FACTORY_WORKSPACE=/home/metation/R_course_via_ai/course_factory_workspace
APPTAINER_IMAGE=/home/metation/R_course_via_ai/course-r.sif
SLURM_PARTITION=cpu
```

## Initialize

```bash
course-factory init
```

## Preflight

Local Apptainer/R validation:

```bash
course-factory preflight --r-packages ggplot2,dplyr
```

Include SLURM command validation:

```bash
course-factory preflight --slurm --r-packages ggplot2,dplyr
```

## Run the smoke test locally

```bash
course-factory execute-r examples/smoke_test.R --executor local
```

## Run the smoke test through SLURM

```bash
course-factory execute-r examples/smoke_test.R \
  --executor slurm \
  --cpus 2 \
  --memory-gb 8 \
  --time-minutes 30 \
  --partition cpu
```

The command prints a job ID. Inspect it with:

```bash
course-factory status JOB_ID
course-factory events JOB_ID
course-factory list
```

## Workspace layout

```text
workspace/
  state/jobs.sqlite3
  jobs/JOB_ID/
    tasks/TASK_ID/
      script.R
      output/
      home/
      tmp/
      logs/
      .course_factory/
        TASK_ID.sbatch
        TASK_ID.exitcode
        TASK_ID.finished
```

## SLURM behavior

This implementation does **not** call `sacct`.

The batch wrapper traps process exit, writes:

```text
TASK_ID.exitcode
TASK_ID.finished
```

The Python supervisor watches these marker files. `squeue` is used
only to detect a job that disappears before producing a marker.
At the configured timeout, the backend invokes `scancel`.
