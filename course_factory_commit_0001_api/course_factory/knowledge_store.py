from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator

SCHEMA = '''
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL,
    url TEXT,
    topic TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    quality_score REAL NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_knowledge_topic
ON knowledge_documents(topic);
CREATE INDEX IF NOT EXISTS idx_knowledge_source_type
ON knowledge_documents(source_type);
CREATE INDEX IF NOT EXISTS idx_knowledge_quality
ON knowledge_documents(quality_score DESC);
'''

class KnowledgeStore:
    def __init__(self, database: str | Path):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA busy_timeout=30000")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.database, timeout=30)
        con.row_factory = sqlite3.Row
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    @staticmethod
    def normalize_text(text: str) -> str:
        return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines()).strip()

    @classmethod
    def content_hash(cls, title: str, source: str, content: str) -> str:
        canonical = "\n".join(
            [title.strip(), source.strip(), cls.normalize_text(content)]
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def insert(
        self,
        *,
        document_id: str,
        title: str,
        source: str,
        source_type: str,
        topic: str,
        content: str,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
        quality_score: float = 1.0,
    ) -> tuple[int, bool]:
        digest = self.content_hash(title, source, content)
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as con:
            existing = con.execute(
                "SELECT id FROM knowledge_documents WHERE content_hash=?",
                (digest,),
            ).fetchone()
            if existing:
                return int(existing["id"]), False
            cur = con.execute(
                '''INSERT INTO knowledge_documents
                (document_id,content_hash,title,source,source_type,url,topic,content,
                 metadata_json,quality_score,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    document_id, digest, title, source, source_type, url, topic,
                    self.normalize_text(content),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    quality_score, now, now,
                ),
            )
            return int(cur.lastrowid), True

    def get_by_document_id(self, document_id: str) -> dict[str, Any] | None:
        with self.connect() as con:
            row = con.execute(
                "SELECT * FROM knowledge_documents WHERE document_id=?",
                (document_id,),
            ).fetchone()
        return self._row(row) if row else None

    def search_topic(self, topic: str, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                '''SELECT * FROM knowledge_documents
                   WHERE lower(topic) LIKE lower(?)
                   ORDER BY quality_score DESC, updated_at DESC
                   LIMIT ?''',
                (f"%{topic}%", limit),
            ).fetchall()
        return [self._row(row) for row in rows]

    def list_documents(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as con:
            rows = con.execute(
                "SELECT * FROM knowledge_documents ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row(row) for row in rows]

    def count(self) -> int:
        with self.connect() as con:
            row = con.execute("SELECT COUNT(*) AS n FROM knowledge_documents").fetchone()
        return int(row["n"])

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json"))
        return data
