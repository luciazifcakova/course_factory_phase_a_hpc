from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


SCHEMA = '''
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    current_step TEXT NOT NULL,
    request_json TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    step TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_id
ON job_events(job_id, event_id);
'''


class SQLiteJobStore:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        with self.connect() as connection:
            connection.executescript(SCHEMA)
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA foreign_keys=ON")

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.database_path,
            timeout=30,
        )
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_job(
        self,
        *,
        job_id: str,
        request: dict[str, Any],
        state: dict[str, Any] | None = None,
    ) -> None:
        now = self._now()
        with self.connect() as connection:
            connection.execute(
                '''
                INSERT INTO jobs(
                    job_id, status, current_step, request_json,
                    state_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    job_id,
                    "created",
                    "initialization",
                    json.dumps(request, default=str),
                    json.dumps(state or {}, default=str),
                    now,
                    now,
                ),
            )

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown job: {job_id}")

        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        result["state"] = json.loads(result.pop("state_json"))
        return result

    def list_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                '''
                SELECT job_id, status, current_step, created_at, updated_at
                FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                ''',
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_job(
        self,
        *,
        job_id: str,
        status: str,
        current_step: str,
        patch: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT state_json FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()

            if row is None:
                raise KeyError(f"Unknown job: {job_id}")

            state = json.loads(row["state_json"])
            if patch:
                state.update(patch)

            connection.execute(
                '''
                UPDATE jobs
                SET status = ?, current_step = ?, state_json = ?,
                    updated_at = ?
                WHERE job_id = ?
                ''',
                (
                    status,
                    current_step,
                    json.dumps(state, default=str),
                    self._now(),
                    job_id,
                ),
            )

    def add_event(
        self,
        *,
        job_id: str,
        step: str,
        message: str,
        level: str = "INFO",
        payload: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                '''
                INSERT INTO job_events(
                    job_id, step, level, message, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (
                    job_id,
                    step,
                    level,
                    message,
                    json.dumps(payload or {}, default=str),
                    self._now(),
                ),
            )

    def list_events(
        self,
        job_id: str,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                '''
                SELECT event_id, job_id, step, level, message,
                       payload_json, created_at
                FROM job_events
                WHERE job_id = ?
                ORDER BY event_id ASC
                LIMIT ?
                ''',
                (job_id, limit),
            ).fetchall()

        events = []
        for row in rows:
            event = dict(row)
            event["payload"] = json.loads(
                event.pop("payload_json")
            )
            events.append(event)
        return events
