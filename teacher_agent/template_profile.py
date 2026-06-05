"""Template profile store.

The profile is not a replacement for template analysis. The analyzer still
reads the current Word file; the profile remembers successful mappings and
repeat-table choices so the Agent can explain and reuse known-good behavior.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class TemplateProfileStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.profiles_dir = self.base_dir / "template_profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

    def template_fingerprint(self, template_path: str | Path) -> str:
        path = Path(template_path)
        if not path.exists():
            return self._safe_id(str(template_path))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:20]
        return f"{self._safe_id(path.name)}-{digest}"

    def _path(self, template_id: str) -> Path:
        return self.profiles_dir / f"{self._safe_id(template_id)}.json"

    def get_or_create(self, template_id: str, template_analysis: dict[str, Any]) -> dict[str, Any]:
        path = self._path(template_id)
        if path.exists():
            try:
                profile = json.loads(path.read_text(encoding="utf-8"))
                profile["profile_hit"] = True
                profile["last_seen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
                return profile
            except (json.JSONDecodeError, OSError):
                pass

        profile = {
            "template_id": template_id,
            "profile_hit": False,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_seen_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mapped_fields": list(template_analysis.get("mapped_fields") or []),
            "table_mappings": template_analysis.get("table_mappings", {}),
            "repeat_fill_mode": "first_only",
            "duplicate_table_policy": "first_only",
            "teaching_method_targets": _targets_for(template_analysis, "teaching_method"),
            "known_risks": _known_risks(template_analysis, None),
            "last_successful_fill": {},
        }
        path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        return profile

    def apply_profile(self, template_analysis: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        """Merge known-good mappings into fresh analysis without hiding current errors."""
        result = dict(template_analysis)
        profile_mappings = profile.get("table_mappings") or {}
        if profile.get("profile_hit") and profile_mappings:
            merged = dict(result.get("table_mappings") or {})
            for field, targets in profile_mappings.items():
                if field not in merged or not merged[field]:
                    merged[field] = targets
            result["table_mappings"] = merged
            mapped = list(result.get("mapped_fields") or [])
            for field in profile.get("mapped_fields") or []:
                if field not in mapped:
                    mapped.append(field)
            result["mapped_fields"] = mapped
            result["profile_applied"] = True
        result["template_profile"] = {
            "template_id": profile.get("template_id"),
            "profile_hit": bool(profile.get("profile_hit")),
            "repeat_fill_mode": profile.get("repeat_fill_mode") or profile.get("duplicate_table_policy"),
            "last_successful_fill": profile.get("last_successful_fill") or {},
        }
        return result

    def save_successful_mapping(
        self,
        template_id: str,
        table_mappings: dict[str, Any],
        fill_report: dict[str, Any],
        *,
        mapped_fields: list[str] | None = None,
        repeat_fill_mode: str | None = None,
        known_risks: list[str] | None = None,
    ) -> None:
        path = self._path(template_id)
        profile = self.get_or_create(template_id, {"mapped_fields": mapped_fields or [], "table_mappings": table_mappings})
        profile["profile_hit"] = True
        profile["mapped_fields"] = mapped_fields or profile.get("mapped_fields") or []
        profile["table_mappings"] = table_mappings
        profile["repeat_fill_mode"] = repeat_fill_mode or profile.get("repeat_fill_mode") or "first_only"
        profile["duplicate_table_policy"] = profile["repeat_fill_mode"]
        profile["teaching_method_targets"] = list(table_mappings.get("teaching_method") or [])
        profile["known_risks"] = known_risks or _known_risks({}, fill_report)
        profile["last_successful_fill"] = {
            "filled_non_empty_count": fill_report.get("filled_non_empty_count"),
            "table_write_count": fill_report.get("table_write_count"),
            "field_write_counts": fill_report.get("field_write_counts"),
            "repeated_sections_detected": fill_report.get("repeated_sections_detected"),
            "filled_sections": fill_report.get("filled_sections"),
        }
        profile["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
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

    @staticmethod
    def _safe_id(value: str) -> str:
        return value.replace("/", "_").replace("\\", "_").replace(":", "_").replace("*", "_")


def _targets_for(template_analysis: dict[str, Any], field: str) -> list[dict[str, Any]]:
    return list((template_analysis.get("table_mappings") or {}).get(field) or [])


def _known_risks(template_analysis: dict[str, Any], fill_report: dict[str, Any] | None) -> list[str]:
    risks: list[str] = []
    risks.extend(str(item) for item in template_analysis.get("errors") or [])
    risks.extend(str(item) for item in template_analysis.get("warnings") or [])
    if fill_report:
        risks.extend(str(item) for item in fill_report.get("errors") or [])
        risks.extend(str(item) for item in fill_report.get("warnings") or [])
        if fill_report.get("remaining_placeholders"):
            risks.append("模板仍可能残留占位符")
    return risks[:12]
