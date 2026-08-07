from __future__ import annotations

from abc import ABC, abstractmethod
import json
from typing import Any, TypeVar

from pydantic import BaseModel
import requests

from .structured_output import (
    extract_first_json_value,
    parse_first_json_value,
)

TModel = TypeVar("TModel", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    def __init__(
        self,
        *,
        model_name: str,
        message: str,
        raw_content: str | None = None,
        extracted_content: str | None = None,
        attempts: int = 1,
    ) -> None:
        super().__init__(
            f"Structured output for {model_name} failed: {message}"
        )
        self.model_name = model_name
        self.raw_content = raw_content
        self.extracted_content = extracted_content
        self.attempts = attempts


class LLMBackend(ABC):
    """
    Structured-output contract.

    Agents supply a Pydantic class. Native providers should convert that
    class to JSON Schema and use provider-level schema/guided decoding.
    Prompt text is not the primary structure-enforcement mechanism.
    """

    @abstractmethod
    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str,
    ) -> dict:
        raise NotImplementedError

    def generate_structured(
        self,
        model_type: type[TModel],
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> TModel:
        """
        Compatibility path for legacy backends that only return dictionaries.
        Native providers should override this method.
        """
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
                    json.dumps(
                        raw,
                        ensure_ascii=False,
                        default=str,
                    )
                    if raw is not None
                    else None
                ),
            ) from exc


class OllamaBackend(LLMBackend):
    """
    Ollama provider with schema-first structured generation.

    Primary enforcement:
        Pydantic model -> model_json_schema() -> Ollama `format`

    Defensive recovery:
        If a model/provider still adds surrounding text or emits more than
        one JSON value, the first complete JSON value is extracted locally
        and then validated by the same Pydantic class.

    Retry:
        The exact same provider-level schema remains authoritative on every
        retry. We do not replace schema enforcement with prompt instructions.
    """

    def __init__(
        self,
        *,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3:14b",
        timeout_seconds: int = 900,
        structured_max_attempts: int = 3,
    ) -> None:
        if structured_max_attempts < 1:
            raise ValueError(
                "structured_max_attempts must be at least one"
            )
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.structured_max_attempts = structured_max_attempts

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
        content = (
            response.json()
            .get("message", {})
            .get("content", "")
        )
        if not content:
            raise RuntimeError(
                "Ollama returned no response content"
            )
        return content

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str,
    ) -> dict:
        """
        Legacy untyped JSON API. New structured agents should call
        generate_structured() with a Pydantic class.
        """
        content = self._chat(
            system=system,
            user=user,
            format_value="json",
            temperature=0.2,
        )
        payload = parse_first_json_value(content)
        if not isinstance(payload, dict):
            raise ValueError(
                "generate_json() expected a JSON object."
            )
        return payload

    def generate_structured(
        self,
        model_type: type[TModel],
        *,
        system: str,
        user: str,
        temperature: float = 0.2,
    ) -> TModel:
        schema = model_type.model_json_schema()

        last_raw: str | None = None
        last_extracted: str | None = None
        last_error: Exception | None = None

        for attempt in range(
            1,
            self.structured_max_attempts + 1,
        ):
            try:
                # Structural enforcement is provider-native here:
                # Ollama receives the Pydantic JSON Schema directly.
                last_raw = self._chat(
                    system=system,
                    user=user,
                    format_value=schema,
                    temperature=temperature,
                )

                # Fast path: exactly one valid JSON value.
                try:
                    return model_type.model_validate_json(
                        last_raw
                    )
                except Exception:
                    # Defensive recovery only. This does not redefine the
                    # schema; it merely isolates the first JSON value when a
                    # provider/model violates its own structured mode.
                    last_extracted = (
                        extract_first_json_value(
                            last_raw
                        )
                    )
                    payload = json.loads(
                        last_extracted
                    )
                    return model_type.model_validate(
                        payload
                    )

            except Exception as exc:
                last_error = exc
                if attempt >= self.structured_max_attempts:
                    break

                # Reissue the same schema-constrained call. The class/schema
                # remains the source of truth on every attempt.
                continue

        raise StructuredOutputError(
            model_name=model_type.__name__,
            message=(
                f"{type(last_error).__name__}: {last_error}"
                if last_error is not None
                else "unknown structured-output error"
            ),
            raw_content=last_raw,
            extracted_content=last_extracted,
            attempts=self.structured_max_attempts,
        ) from last_error


class StaticJSONBackend(LLMBackend):
    def __init__(self, response: dict) -> None:
        self.response = response

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str,
    ) -> dict:
        return dict(self.response)


class LegacyBackendAdapter(LLMBackend):
    def __init__(self, backend: Any) -> None:
        self.backend = backend

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema_hint: str,
    ) -> dict:
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
    raise TypeError(
        "LLM backend must implement generate_structured() "
        "or generate_json()."
    )
