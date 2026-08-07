# Commit 005.1 — Preserve the real slide-agent failure

## Commit message

```text
fix(agents): preserve diagnostics on failed slide generation

- extend AgentResult.failed() with optional outputs and metrics
- keep existing AgentResult.failed() calls backward compatible
- allow slide planner/generator to return bounded attempt diagnostics
- persist slide_planning_failure.json on planner failure
- persist slide_generation_failure.json on content-generation failure
- stop exception-reporting code from masking the underlying slide error
- add regression tests for failed AgentResult diagnostic payloads
```

This commit intentionally does not guess at the underlying slide failure.
After applying it, the next HPC run will report the actual planner or
slide-generation validation error instead of:

`AgentResult.failed() got an unexpected keyword argument 'outputs'`.
