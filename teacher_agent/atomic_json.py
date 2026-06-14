from __future__ import annotations

import json
import os
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


_LOCKS_GUARD = threading.Lock()
_PATH_LOCKS: dict[str, threading.RLock] = {}
_REPLACE_ATTEMPTS = 5
_REPLACE_RETRY_DELAY_SECONDS = 0.01


def _lock_for(path: str | Path) -> threading.RLock:
    key = str(Path(path).resolve())
    with _LOCKS_GUARD:
        return _PATH_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def json_path_lock(path: str | Path) -> Iterator[None]:
    with _lock_for(path):
        yield


def read_json(path: str | Path, default: Any = None) -> Any:
    target = Path(path)
    with json_path_lock(target):
        if not target.exists():
            return default
        return json.loads(target.read_text(encoding="utf-8"))


def _replace_with_retry(source: Path, target: Path) -> None:
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_RETRY_DELAY_SECONDS * (attempt + 1))


def atomic_write_json(path: str | Path, value: Any, *, indent: int | None = None) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with json_path_lock(target):
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(value, file, ensure_ascii=False, indent=indent)
                file.flush()
                os.fsync(file.fileno())
            _replace_with_retry(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
