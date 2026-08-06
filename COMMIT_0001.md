# Commit 0001

## Commit message

```text
feat(api): add create-course API and outline pipeline

- add stable CourseFactoryAPI
- add JobManager and PipelineRunner
- add typed create-course request and response models
- connect InputBuilderAgent and CoursePlannerAgent
- persist course specification and outline as JSON artifacts
- record job progress and failures in SQLite
- add create-course CLI command
- add Ollama settings
- add ggplot2 example request and integration tests
```

## Run

```bash
cp .env.example .env
# Set OLLAMA_MODEL and OLLAMA_BASE_URL if needed.

course-factory create-course \
  --prompt "Create an introduction to ggplot2 course" \
  --duration-minutes 180 \
  --audience "Scientists new to R visualization" \
  --r-packages ggplot2
```

Or:

```bash
course-factory create-course \
  --request-file examples/ggplot2_course.yaml
```

This first commit creates:

```text
workspace/jobs/JOB_ID/course_specification.json
workspace/jobs/JOB_ID/course_outline.json
```

Slides, generated R scripts, execution and PowerPoint are deliberately
left for subsequent commits.
