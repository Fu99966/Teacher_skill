from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SQLITE_BUSY_TIMEOUT_MS = 30_000


@contextmanager
def managed_sqlite_connection(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(
        str(db_path),
        timeout=SQLITE_BUSY_TIMEOUT_MS / 1000,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
