# Commit 005.4 — Schema-first structured output backend

```text
refactor(llm): enforce structured outputs through provider schemas

- keep Pydantic classes as the source of truth
- pass model_json_schema() directly to Ollama's `format` field
- do not inject JSON Schema into native structured prompts
- add balanced first-JSON extraction as provider-defect recovery
- recover from fences, leading/trailing prose and multiple JSON values
- validate all recovered payloads with the original Pydantic class
- retry the same schema-constrained provider call on validation failure
- preserve raw and extracted content in StructuredOutputError
- retain generate_json only for legacy compatibility
- add regression coverage for trailing-character slide JSON failures
```

Architecture:

Pydantic class
    -> JSON Schema
    -> provider-native structured mode
    -> response
    -> direct Pydantic validation
       or defensive first-JSON extraction
    -> Pydantic instance

Prompt wording is not the primary structure-enforcement mechanism.
