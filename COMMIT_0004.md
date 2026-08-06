# Commit 004

## Commit message

```text
feat(execution): execute approved R scripts with Apptainer and SLURM

- add create-course executor selection: none, local or slurm
- execute approved R scripts in isolated per-task directories
- run R only inside the configured Apptainer image
- reuse marker-based SLURM monitoring without sacct
- add local execution timeout handling
- validate every expected output
- collect generated files with size and SHA-256 metadata
- persist execution_report.json and execution progress
- expose generated figures/tables as course artifacts
- add execution service and routing tests
```

## Generate only

```bash
course-factory create-course \
  --prompt "Create an introduction to ggplot2 course" \
  --duration-minutes 180 \
  --audience "Scientists new to R visualization" \
  --r-packages ggplot2 \
  --executor none
```

## Execute locally through Apptainer

```bash
course-factory create-course \
  --prompt "Create an introduction to ggplot2 course" \
  --duration-minutes 180 \
  --audience "Scientists new to R visualization" \
  --r-packages ggplot2 \
  --executor local
```

## Execute through SLURM

```bash
course-factory create-course \
  --prompt "Create an introduction to ggplot2 course" \
  --duration-minutes 180 \
  --audience "Scientists new to R visualization" \
  --r-packages ggplot2 \
  --executor slurm \
  --cpus 2 \
  --memory-gb 8 \
  --time-minutes 60 \
  --partition cpu
```

Successful execution ends at:

```json
{
  "status": "completed",
  "current_step": "r_execution_complete"
}
```
