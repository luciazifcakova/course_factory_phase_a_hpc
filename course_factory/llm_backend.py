from __future__ import annotations
from abc import ABC, abstractmethod
import json
import requests

class LLMBackend(ABC):
    @abstractmethod
    def generate_json(self, *, system: str, user: str, schema_hint: str) -> dict:
        raise NotImplementedError

class OllamaBackend(LLMBackend):
    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3:14b",
        timeout_seconds: int = 900,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_json(self, *, system: str, user: str, schema_hint: str) -> dict:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": user + "\n\nReturn only valid JSON matching:\n" + schema_hint,
                    },
                ],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Ollama returned no JSON content")
        return json.loads(content)

class StaticJSONBackend(LLMBackend):
    def __init__(self, response: dict) -> None:
        self.response = response

    def generate_json(self, *, system: str, user: str, schema_hint: str) -> dict:
        return dict(self.response)
