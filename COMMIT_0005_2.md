# Commit 005.2

```text
fix(slides): resolve lesson code paths from the artifact manifest

- remove code_artifact path selection from the LLM slide-plan schema
- replace it with use_code: bool
- expose only code_available to the planner
- resolve the exact lesson script path deterministically from the manifest
- preserve final Slide.code_artifact for PowerPoint rendering
- prevent path/case/format variations from causing false validation failures
```
