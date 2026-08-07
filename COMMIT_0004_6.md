# Commit 004.6

## Commit message

```text
fix(planning): bound course size and reject empty successful runs

- require at least one course learning objective
- prompt input builder for 3-6 concrete objectives
- hard-limit course plans to 1-8 modules
- require 1-8 lessons in every module
- cap dependency arrays at four IDs
- cap identifiers and other planner collections
- require dependencies to reference earlier items only
- reject severely underfilled or oversized course plans
- never echo huge malformed LLM output into repair prompts
- preserve full raw malformed output only in trace files
- reject zero-lesson plans before downstream generation
- reject zero-success execution before marking completion
```
