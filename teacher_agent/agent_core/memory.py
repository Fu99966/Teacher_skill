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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS teacher_field_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    template_id TEXT NOT NULL,
                    subject TEXT,
                    grade TEXT,
                    title TEXT,
                    class_type TEXT,
                    fields_json TEXT NOT NULL
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

    def remember_teacher_edit(
        self,
        *,
        template_id: str,
        task: dict[str, Any],
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        created_at = time.strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO teacher_field_feedback (
                    created_at, template_id, subject, grade, title, class_type, fields_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    template_id,
                    str(task.get("subject") or ""),
                    str(task.get("grade") or ""),
                    str(task.get("title") or task.get("lesson_title") or ""),
                    str(task.get("class_type") or ""),
                    json.dumps(fields, ensure_ascii=False),
                ),
            )
        return {"id": cursor.lastrowid, "created_at": created_at, "template_id": template_id}

    def find_teacher_edit_examples(
        self,
        *,
        subject: str = "",
        grade: str = "",
        title: str = "",
        template_id: str = "",
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        conditions = []
        values: list[Any] = []
        if template_id:
            conditions.append("template_id = ?")
            values.append(template_id)
        if subject:
            conditions.append("(subject LIKE ? OR title LIKE ?)")
            values.extend([f"%{subject}%", f"%{title or subject}%"])
        if grade:
            conditions.append("(grade LIKE ? OR title LIKE ?)")
            values.extend([f"%{grade}%", f"%{title or grade}%"])
        where = "WHERE " + " OR ".join(conditions) if conditions else ""
        values.append(limit)
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT created_at, template_id, subject, grade, title, class_type, fields_json
                FROM teacher_field_feedback
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                values,
            ).fetchall()

        examples: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                fields = json.loads(str(item.pop("fields_json") or "{}"))
            except json.JSONDecodeError:
                fields = {}
            item["fields"] = fields
            examples.append(item)
        return examples
