from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4


def safe_filename(value: str, fallback: str = "lesson", max_length: int = 80) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value or "")).strip(" ._")
    return cleaned[:max_length] or fallback


def unique_artifact_name(value: str, suffix: str, fallback: str = "lesson") -> str:
    normalized_suffix = suffix if suffix.startswith(".") else f".{suffix}"
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    unique_token = uuid4().hex[:10]
    return f"{safe_filename(value, fallback)}-{timestamp}-{unique_token}{normalized_suffix}"


def unique_upload_name(original_name: str, fallback: str = "template") -> str:
    original = Path(original_name).name
    suffix = Path(original).suffix.lower() or ".bin"
    stem = Path(original).stem
    return unique_artifact_name(stem, suffix, fallback)
