# Commit 003.1

## Commit message

```text
fix(r): harden typed R generation and preserve failed LLM responses

- replace direct response["code"] access with RCodeLLMResponse validation
- accept script/r_script as compatibility aliases and canonicalize to code
- remove accidental Markdown code fences
- retry invalid model responses up to three times with validation feedback
- persist exact requests and raw responses for every attempt
- preserve partial generation progress after every lesson
- add structured attempt and failure details to generation reports
- write r_code_generation_report.json before raising task-level failure
- add regression tests for missing code, aliases, retries and raw traces
```

## Debugging layout

```text
workspace/jobs/JOB_ID/
  r_code_generation_report.json
  r_code_generation_progress.json
  llm/
    r_code_generation/
      LES-001.r_code/
        attempt_01_request.json
        attempt_01_response.json
        attempt_02_request.json
        attempt_02_response.json
  scripts/
    LES-001.R
```

A missing `code` field now produces a typed validation error, is sent
back to the model for repair, and remains visible in the job trace.
