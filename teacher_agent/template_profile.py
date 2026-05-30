"""Template Profile – remember successful mappings across sessions."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TemplateProfileStore:
    """Persist known-good table mappings per template to avoid repeated diagnostics."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.profiles_dir = self.base_dir / "template_profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, template_id: str) -> Path:
        safe = template_id.replace("/", "_").replace("\\", "_").replace(":", "_")
        return self.profiles_dir / f"{safe}.json"

    def get_or_create(self, template_id: str, template_analysis: dict[str, Any]) -> dict[str, Any]:
        path = self._path(template_id)
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        profile = {
            "template_id": template_id,
            "mapped_fields": template_analysis.get("mapped_fields", []),
            "table_mappings": template_analysis.get("table_mappings", {}),
            "duplicate_table_policy": "all",
            "known_risks": template_analysis.get("errors", []),
            "last_successful_fill": {},
        }
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        return profile

    def save_successful_mapping(
        self, template_id: str, table_mappings: dict[str, Any], fill_report: dict[str, Any]
    ) -> None:
        path = self._path(template_id)
        profile = {"template_id": template_id, "mapped_fields": [], "table_mappings": {}, "duplicate_table_policy": "all", "known_risks": [], "last_successful_fill": {}}
        if path.exists():
            try:
                profile = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        profile["table_mappings"] = table_mappings
        profile["last_successful_fill"] = {
            "filled_non_empty_count": fill_report.get("filled_non_empty_count"),
            "table_write_count": fill_report.get("table_write_count"),
            "field_write_counts": fill_report.get("field_write_counts"),
        }
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_known_targets(self, template_id: str) -> dict[str, Any] | None:
        path = self._path(template_id)
        if not path.exists():
            return None
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
            return profile.get("table_mappings")
        except (json.JSONDecodeError, OSError):
            return None
