from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, ContextManager

from ..sqlite_store import managed_sqlite_connection


_MEMORY_IDENTITY_FIELDS = {
    "lesson_title",
    "title",
    "subject",
    "grade",
    "class_name",
    "class_hour",
    "class_type",
    "teaching_date",
}


def _memory_key(value: Any) -> str:
    return re.sub(r"[\s\u3000《》“”\"'，,。.:：;；、\-_/\\|()（）\[\]【】{}]+", "", str(value or "")).upper()


def _non_empty_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item).strip() for item in value if str(item).strip()).strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False).strip() if value else ""
    return str(value).strip()


def build_teacher_memory_context(examples: list[dict[str, Any]], limit: int = 2) -> str:
    """Build a prompt-only teacher preference context without polluting material/RAG."""
    notes: list[str] = []
    for item in examples[:limit]:
        fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
        preferred = []
        for key in ("teaching_goals", "teaching_process", "teaching_method", "homework", "reflection"):
            value = _non_empty_text(fields.get(key))
            if value:
                preferred.append(f"{key}={value[:260]}")
        if preferred:
            notes.append(
                f"老师历史修改样例（课题：{item.get('title', '')}；课型：{item.get('class_type', '')}）："
                + "；".join(preferred)
            )
    return "\n".join(notes)


def apply_exact_teacher_edit_memory(
    generated_fields: dict[str, Any],
    examples: list[dict[str, Any]],
    *,
    title: str,
    class_hour: str,
    grade: str,
    class_type: str,
    template_id: str,
) -> tuple[dict[str, Any], list[str]]:
    """Reuse exact-match teacher edits for local fallback without overwriting identity fields."""
    result = dict(generated_fields or {})
    title_key = _memory_key(title)
    hour_key = _memory_key(class_hour)
    grade_key = _memory_key(grade)
    class_type_key = _memory_key(class_type)
    template_key = str(template_id or "")
    reused: list[str] = []

    for item in examples:
        if not item.get("exact_title_match") or _memory_key(item.get("title")) != title_key:
            continue
        if template_key and str(item.get("template_id") or "") != template_key:
            continue
        if grade_key and _memory_key(item.get("grade")) and _memory_key(item.get("grade")) != grade_key:
            continue
        if class_type_key and _memory_key(item.get("class_type")) and _memory_key(item.get("class_type")) != class_type_key:
            continue
        fields = item.get("fields") if isinstance(item.get("fields"), dict) else {}
        remembered_hour = _memory_key(fields.get("class_hour"))
        if hour_key and remembered_hour and hour_key != remembered_hour:
            continue
        for field, value in fields.items():
            if field in _MEMORY_IDENTITY_FIELDS:
                continue
            text = _non_empty_text(value)
            if not text:
                continue
            result[field] = text
            if field not in reused:
                reused.append(field)
        break
    return result, reused


class AgentMemoryStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> ContextManager[sqlite3.Connection]:
        return managed_sqlite_connection(self.db_path)

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
        class_type: str = "",
        template_id: str = "",
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT created_at, template_id, subject, grade, title, class_type, fields_json
                FROM teacher_field_feedback
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(limit * 20, 40),),
            ).fetchall()

        examples: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            try:
                fields = json.loads(str(item.pop("fields_json") or "{}"))
            except json.JSONDecodeError:
                fields = {}
            item["fields"] = fields
            score = 0
            exact_title_match = bool(title and _memory_key(item.get("title")) == _memory_key(title))
            if exact_title_match:
                score += 12
            if template_id and str(item.get("template_id") or "") == str(template_id):
                score += 6
            if subject and _memory_key(item.get("subject")) == _memory_key(subject):
                score += 3
            if grade and _memory_key(item.get("grade")) == _memory_key(grade):
                score += 2
            if class_type and _memory_key(item.get("class_type")) == _memory_key(class_type):
                score += 2
            if title and _memory_key(title) in _memory_key(item.get("title")):
                score += 2
            semantic_match = any(
                (
                    exact_title_match,
                    bool(subject and _memory_key(item.get("subject")) == _memory_key(subject)),
                    bool(grade and _memory_key(item.get("grade")) == _memory_key(grade)),
                    bool(class_type and _memory_key(item.get("class_type")) == _memory_key(class_type)),
                )
            )
            if any((subject, grade, title, class_type)) and not semantic_match:
                continue
            if not any((subject, grade, title, class_type, template_id)):
                score = 1
            if score <= 0:
                continue
            item["match_score"] = score
            item["exact_title_match"] = exact_title_match
            examples.append(item)
        examples.sort(key=lambda item: (int(item.get("match_score") or 0), str(item.get("created_at") or "")), reverse=True)
        return examples[:limit]
