from __future__ import annotations

from typing import Any


_CHECK_TO_FIELD = {
    "goals_specific": "teaching_goals",
    "key_difficult_clear": "teaching_key_difficult",
    "process_structure": "teaching_process",
    "method_specific": "teaching_method",
    "homework_layered": "homework",
    "reflection_meaningful": "reflection",
}


def revise_fields_from_pedagogy_review(
    fields: dict[str, Any],
    review_report: dict[str, Any],
    task: dict[str, Any],
    *,
    allowed_fields: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Replace only fields that failed the rule-based pedagogy review."""
    result = dict(fields or {})
    allowed = set(result.keys() if allowed_fields is None else allowed_fields)
    failed_fields = _failed_review_fields(review_report, allowed)
    if not failed_fields:
        return result, []

    from ..lesson_generator import _local_fallback_fields, normalize_lesson_field_aliases

    fallback = _local_fallback_fields(
        subject=str(task.get("subject") or result.get("subject") or ""),
        grade=str(task.get("grade") or result.get("grade") or ""),
        title=str(task.get("title") or result.get("lesson_title") or "未命名课题"),
        material=str(task.get("material") or ""),
        class_hour=str(task.get("class_hour") or result.get("class_hour") or "1课时"),
        class_type=str(task.get("class_type") or result.get("class_type") or ""),
        dynamic_fields=failed_fields,
    )

    changed: list[str] = []
    for field in failed_fields:
        replacement = str(fallback.get(field) or "").strip()
        if not replacement or replacement == str(result.get(field) or "").strip():
            continue
        result[field] = replacement
        changed.append(field)

    return normalize_lesson_field_aliases(result, str(task.get("raw_text") or "")), changed


def _failed_review_fields(review_report: dict[str, Any], allowed: set[str]) -> list[str]:
    failed: list[str] = []
    for check in review_report.get("pedagogy_checks") or []:
        if check.get("passed", False):
            continue
        field = _CHECK_TO_FIELD.get(str(check.get("name") or ""))
        if field and field in allowed and field not in failed:
            failed.append(field)
    return failed
