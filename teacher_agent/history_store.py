from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any


class HistoryStore:
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
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    class_type TEXT,
                    teaching_style TEXT,
                    backend TEXT,
                    template_mode TEXT,
                    output_name TEXT NOT NULL,
                    download_url TEXT NOT NULL,
                    preview_url TEXT,
                    fields_json TEXT NOT NULL,
                    review_json TEXT,
                    trace_json TEXT
                )
                """
            )

    def save_document(
        self,
        *,
        fields: dict[str, Any],
        request_context: dict[str, Any] | None,
        generation_backend: str,
        template_mode: str,
        output_name: str,
        download_url: str,
        preview_url: str | None,
        review_report: dict[str, Any] | None = None,
        workflow_trace: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        record = {
            "id": uuid.uuid4().hex,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "title": str(fields.get("lesson_title") or "未命名教案"),
            "subject": str(fields.get("subject") or ""),
            "grade": str(fields.get("grade") or ""),
            "class_type": str((request_context or {}).get("class_type") or ""),
            "teaching_style": str((request_context or {}).get("teaching_style") or ""),
            "backend": generation_backend,
            "template_mode": template_mode,
            "output_name": output_name,
            "download_url": download_url,
            "preview_url": preview_url,
            "fields_json": json.dumps(fields, ensure_ascii=False),
            "review_json": json.dumps(review_report or {}, ensure_ascii=False),
            "trace_json": json.dumps(workflow_trace or [], ensure_ascii=False),
        }
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents (
                    id, created_at, title, subject, grade, class_type, teaching_style,
                    backend, template_mode, output_name, download_url, preview_url,
                    fields_json, review_json, trace_json
                ) VALUES (
                    :id, :created_at, :title, :subject, :grade, :class_type, :teaching_style,
                    :backend, :template_mode, :output_name, :download_url, :preview_url,
                    :fields_json, :review_json, :trace_json
                )
                """,
                record,
            )
        return self._public_record(record)

    def list_documents(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, title, subject, grade, class_type, teaching_style,
                       backend, template_mode, output_name, download_url, preview_url
                FROM documents
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _public_record(self, record: dict[str, Any]) -> dict[str, Any]:
        return {
            key: record[key]
            for key in (
                "id",
                "created_at",
                "title",
                "subject",
                "grade",
                "class_type",
                "teaching_style",
                "backend",
                "template_mode",
                "output_name",
                "download_url",
                "preview_url",
            )
        }
