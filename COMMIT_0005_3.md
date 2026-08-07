# Commit 005.3 — Deterministic slide resolution

```text
refactor(slides): move layout and artifact assignment out of the LLM

- add LLM-facing SlideIntentKind / LessonSlideIntent models
- remove layouts, figure paths and script paths from LLM slide planning
- add deterministic SlideLayoutResolver
- map overview/exercise/summary/code intents to layouts in Python
- assign validated lesson figures in Python, preferring PNG over PDF
- degrade visual intent to bullets when no figure exists
- resolve code layout only when a lesson script exists
- add deterministic slides for unused validated lesson figures
- keep LessonSlidePlan as the downstream rendering contract
- add regression tests for the empty-figure failure
```
