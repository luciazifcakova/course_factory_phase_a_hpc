# Commit 0002

## Commit message

```text
feat(lessons): generate structured Markdown course lessons

- add typed lesson-content models
- generate one validated content object per planned lesson
- preserve planned lesson IDs, titles and source IDs
- require practical activities for practical lessons
- render deterministic Markdown lesson files and course index
- persist lesson_content.json and Markdown artifacts
- expose lesson-generation progress through SQLite job events
- fix create-course CLI dispatch regression
- add API, renderer, validation and CLI regression tests
```

## Result

```text
workspace/jobs/JOB_ID/
  course_specification.json
  course_outline.json
  lesson_content.json
  lessons/
    README.md
    01_<lesson>.md
    02_<lesson>.md
    ...
```

## Run

```bash
course-factory create-course   --prompt "Create an introduction to ggplot2 course"   --duration-minutes 180   --audience "Scientists new to R visualization"   --r-packages ggplot2
```

Successful output now reports:

```json
{
  "status": "completed",
  "current_step": "lessons_complete"
}
```
