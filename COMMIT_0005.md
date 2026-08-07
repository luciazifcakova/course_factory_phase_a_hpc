# Commit 005 — Structured slide planning and generation

## Commit message

```text
feat(slides): generate manifest-grounded structured lesson slides

- add SlidePlannerAgent with strict Pydantic structured output
- plan slides one lesson at a time from lesson content + artifact manifest
- reject figure/R-script references not present in that lesson
- add bounded repair loops with saved request/response traces
- separate slide structure planning from slide prose generation
- make artifact references and layouts immutable after planning
- generate titles, bullets and speaker notes in a second structured stage
- deterministically merge prose with validated artifact references
- support up to two figures per slide
- preserve legacy figure_artifact for the existing PPT builder
- write slide_plan.json and slide_deck.json
- write per-lesson slides/LES-XXX.json
- write slide_generation_report.json
- make the CLI request slides by default
```
