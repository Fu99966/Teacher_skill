from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class AgentMemoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memory (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def remember_agent_run(
        self,
        *,
        task: dict[str, Any],
        template_id: str,
        output_name: str,
        evaluation_passed: bool,
    ) -> None:
        self.set(
            "last_lesson_plan",
            {
                "task": task,
                "template_id": template_id,
                "output_name": output_name,
                "evaluation_passed": evaluation_passed,
            },
        )

    def set(self, key: str, value: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_memory (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), time.strftime("%Y-%m-%d %H:%M:%S")),
            )

    def get(self, key: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value_json FROM agent_memory WHERE key = ?", (key,)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["value_json"])
        except json.JSONDecodeError:
            return None
