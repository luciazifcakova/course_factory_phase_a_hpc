from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
import math
import requests

class EmbeddingBackend(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

class OllamaEmbeddingBackend(EmbeddingBackend):
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "nomic-embed-text",
        timeout_seconds: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        response = requests.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        vector = response.json().get("embedding")
        if not isinstance(vector, list) or not vector:
            raise RuntimeError("Ollama returned no embedding")
        return [float(value) for value in vector]

class EmbeddingService:
    def __init__(self, backend: EmbeddingBackend):
        self.backend = backend

    @staticmethod
    def normalize(vector: Sequence[float]) -> list[float]:
        norm = math.sqrt(sum(float(x) ** 2 for x in vector))
        if norm == 0:
            raise ValueError("cannot normalize a zero vector")
        return [float(x) / norm for x in vector]

    def embed_document(self, title: str, content: str) -> list[float]:
        return self.normalize(self.backend.embed(f"{title}\n\n{content}"))

    def embed_query(self, query: str) -> list[float]:
        return self.normalize(self.backend.embed(query))

    def embed_many(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.normalize(self.backend.embed(text)) for text in texts]
