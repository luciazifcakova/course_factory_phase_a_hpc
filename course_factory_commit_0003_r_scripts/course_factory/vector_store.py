from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

class VectorStore(ABC):
    @abstractmethod
    def upsert(
        self,
        *,
        item_id: str,
        embedding: list[float],
        metadata: dict[str, Any],
        document: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        *,
        embedding: list[float],
        limit: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, item_id: str) -> None:
        raise NotImplementedError

class ChromaVectorStore(VectorStore):
    def __init__(self, path: str, collection: str = "course_factory"):
        import chromadb
        self.client = chromadb.PersistentClient(path=path)
        self.collection = self.client.get_or_create_collection(collection)

    def upsert(self, *, item_id, embedding, metadata, document):
        self.collection.upsert(
            ids=[item_id],
            embeddings=[embedding],
            metadatas=[metadata],
            documents=[document],
        )

    def search(self, *, embedding, limit=5, where=None):
        kwargs = {
            "query_embeddings": [embedding],
            "n_results": limit,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        result = self.collection.query(**kwargs)
        ids = result["ids"][0]
        docs = result["documents"][0]
        metas = result["metadatas"][0]
        distances = result["distances"][0]
        return [
            {
                "id": ids[i],
                "document": docs[i],
                "metadata": metas[i],
                "distance": float(distances[i]),
            }
            for i in range(len(ids))
        ]

    def delete(self, item_id: str):
        self.collection.delete(ids=[item_id])

class InMemoryVectorStore(VectorStore):
    def __init__(self):
        self._items: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def upsert(self, *, item_id, embedding, metadata, document):
        self._items[item_id] = {
            "embedding": list(embedding),
            "metadata": dict(metadata),
            "document": document,
        }

    def search(self, *, embedding, limit=5, where=None):
        rows = []
        for item_id, item in self._items.items():
            if where and any(item["metadata"].get(k) != v for k, v in where.items()):
                continue
            similarity = self._cosine(embedding, item["embedding"])
            rows.append({
                "id": item_id,
                "document": item["document"],
                "metadata": item["metadata"],
                "distance": 1.0 - similarity,
            })
        rows.sort(key=lambda row: row["distance"])
        return rows[:limit]

    def delete(self, item_id: str):
        self._items.pop(item_id, None)
