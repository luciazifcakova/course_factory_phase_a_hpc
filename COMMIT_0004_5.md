# Commit 004.5

## Commit message

```text
fix(planner): separate background prerequisites from graph dependency IDs

- add planner-specific Pydantic models for modules and lessons
- expose prerequisite_module_ids and prerequisite_lesson_ids to Ollama
- constrain dependency IDs to machine-readable identifiers without spaces
- validate that every dependency ID exists in the same generated plan
- reject self-dependencies before scheduling
- keep CourseSpecification.prerequisites for human/background knowledge only
- add a bounded planner repair loop for invalid structured or semantic output
- persist planner requests, responses and validation traces
- retain legacy `prerequisites` aliases for old tests/custom backends
- add regression tests for natural-language and unknown prerequisite IDs
```

The production Ollama schema now distinguishes:

```text
CourseSpecification.prerequisites
    = ["basic R programming knowledge"]

PlannerModule.prerequisite_module_ids
    = ["mod_001"]

PlannerLesson.prerequisite_lesson_ids
    = ["LES-001"]
```

Natural-language background requirements can no longer validate as
module/lesson dependency IDs.
