# Commit 004.3

## Commit message

```text
fix(lessons): retry malformed lesson JSON with schema feedback

- add bounded lesson-generation repair loop
- persist lesson requests, raw responses and validation errors
- explicitly constrain sections vs key_takeaways structure
- feed exact Pydantic validation errors back to the LLM
- add lesson generation attempt/retry metrics
- add regression test for malformed sections output
```
