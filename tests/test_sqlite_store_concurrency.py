from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from teacher_agent.agent_core.memory import AgentMemoryStore
from teacher_agent.history_store import HistoryStore


def _history_fields(index: int) -> dict[str, str]:
    return {
        "lesson_title": f"并发教案 {index}",
        "subject": "物联网",
        "grade": "24级物联网班",
    }


@pytest.mark.parametrize("store_class", [HistoryStore, AgentMemoryStore])
def test_sqlite_store_connections_are_wal_configured_and_closed(store_class, tmp_path):
    store = store_class(tmp_path / f"{store_class.__name__}.sqlite3")

    with store._connect() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]

    assert journal_mode == "wal"
    assert busy_timeout >= 30_000
    assert foreign_keys == 1
    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1")


def test_history_store_accepts_concurrent_teacher_exports(tmp_path):
    store = HistoryStore(tmp_path / "history.sqlite3")

    def save(index: int) -> None:
        store.save_document(
            fields=_history_fields(index),
            request_context={"class_type": "新授课"},
            generation_backend="local_fallback",
            template_mode="system",
            output_name=f"lesson-{index}.docx",
            download_url=f"/download/lesson-{index}.docx",
            preview_url=None,
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(save, range(40)))

    assert len(store.list_documents(limit=50)) == 40
