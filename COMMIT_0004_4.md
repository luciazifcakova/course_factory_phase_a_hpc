# Commit 004.4

## Commit message

```text
refactor(llm): enforce Pydantic schemas at structured LLM boundaries

- add backend.generate_structured(PydanticModel, system=..., user=...)
- send model_json_schema() directly to Ollama's `format` field
- return typed Pydantic objects before downstream processing
- retain generate_json for backward compatibility
- adapt legacy/custom generate_json-only backends automatically
- migrate course specification, planner, lesson, R code, evidence,
  assessment, exercise, slide, repair and R-execution repair generation
- keep semantic validation after structural validation
- preserve raw invalid Ollama content in StructuredOutputError
```

Production code now uses:

```python
lesson = backend.generate_structured(
    LessonContent,
    system=system_prompt,
    user=user_prompt,
)
```

The downstream pipeline therefore receives a validated LessonContent object,
rather than an arbitrary dictionary.
