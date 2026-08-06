from __future__ import annotations
import os
from .input_builder_agent import InputBuilderAgent
from .llm_backend import OllamaBackend

def build_input_builder_agent() -> InputBuilderAgent:
    return InputBuilderAgent(
        OllamaBackend(
            base_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
            model=os.getenv("OLLAMA_MODEL", "qwen3:14b"),
            timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "900")),
        )
    )
