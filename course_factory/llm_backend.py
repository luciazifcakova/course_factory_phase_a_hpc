from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any, TypeVar

from pydantic import BaseModel
import requests

TModel = TypeVar("TModel", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    def __init__(
        self,
        *,
        model_name: str,
        message: str,
        raw_content: str | None = None,
    ) -> None:
        super().__init__(f"Structured output for {model_name} failed: {message}")
        self.model_name = model_name
        self.raw_content = raw_content


class LLMBackend(ABC):
    @abstractmethod
    def generate_json(self, *, system: str, user: str, schema_hint: str) -> dict:
        raise NotImplementedError

    def generate_structured(
        self,
        model_type: type[TModel],
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> TModel:
        raw = None
        try:
            raw = self.generate_json(
                system=system,
                user=user,
                schema_hint=json.dumps(
                    model_type.model_json_schema(),
                    ensure_ascii=False,
                ),
            )
            return model_type.model_validate(raw)
        except Exception as exc:
            raise StructuredOutputError(
                model_name=model_type.__name__,
                message=f"{type(exc).__name__}: {exc}",
                raw_content=(
                    json.dumps(raw, ensure_ascii=False, default=str)
                    if raw is not None else None
                ),
            ) from exc


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

    def _chat(
        self,
        *,
        system: str,
        user: str,
        format_value: str | dict,
        temperature: float,
    ) -> str:
        response = requests.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "format": format_value,
                "options": {"temperature": temperature},
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        content = response.json().get("message", {}).get("content", "")
        if not content:
            raise RuntimeError("Ollama returned no response content")
        return content

    def generate_json(self, *, system: str, user: str, schema_hint: str) -> dict:
        content = self._chat(
            system=system,
            user=user + "\n\nReturn only valid JSON matching:\n" + schema_hint,
            format_value="json",
            temperature=0.2,
        )
        return json.loads(content)

    def generate_structured(
        self,
        model_type: type[TModel],
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> TModel:
        content = None
        try:
            content = self._chat(
                system=system + "\nReturn only data conforming to the supplied JSON schema.",
                user=user,
                format_value=model_type.model_json_schema(),
                temperature=temperature,
            )
            return model_type.model_validate_json(content)
        except Exception as exc:
            raise StructuredOutputError(
                model_name=model_type.__name__,
                message=f"{type(exc).__name__}: {exc}",
                raw_content=content,
            ) from exc


class StaticJSONBackend(LLMBackend):
    def __init__(self, response: dict) -> None:
        self.response = response

    def generate_json(self, *, system: str, user: str, schema_hint: str) -> dict:
        return dict(self.response)


class LegacyBackendAdapter(LLMBackend):
    def __init__(self, backend: Any) -> None:
        self.backend = backend

    def generate_json(self, *, system: str, user: str, schema_hint: str) -> dict:
        return self.backend.generate_json(
            system=system,
            user=user,
            schema_hint=schema_hint,
        )


def ensure_structured_backend(backend: Any):
    if isinstance(backend, LLMBackend):
        return backend
    if hasattr(backend, "generate_structured"):
        return backend
    if hasattr(backend, "generate_json"):
        return LegacyBackendAdapter(backend)
    raise TypeError("LLM backend must implement generate_structured() or generate_json().")
