"""Repair agent – diagnose and attempt to fix failed execution states."""
from __future__ import annotations

from typing import Any

from .state import AgentRunState


def diagnose_failure(state: AgentRunState) -> dict[str, Any]:
    """Return an analysis dict describing what went wrong."""
    issues: list[str] = []
    suggestions: list[str] = []

    fields = state.fields or {}
    er = state.evaluation_report or {}
    fr = (state.export_result or {}).get("fill_report", {}) if state.export_result else {}

    # Check fields
    if not fields:
        issues.append("fields 为空，未生成任何教案内容。")
        suggestions.append("重新生成字段")
    else:
        non_empty = sum(1 for v in fields.values() if str(v or "").strip())
        if non_empty == 0:
            issues.append("所有字段内容为空。")
            suggestions.append("使用 local fallback 填充所有字段")

    # Check fill report
    if isinstance(fr, dict):
        if fr.get("filled_non_empty_count", 0) == 0:
            issues.append("Word 中未写入任何非空字段（filled_non_empty_count == 0）。")
            suggestions.append("阻止导出，提示老师使用占位符模板或检查模板结构")
        missing = fr.get("missing_fields", [])
        if missing:
            issues.append(f"缺失字段：{', '.join(missing)}。")
            suggestions.append(f"用 fallback 补齐缺失字段：{', '.join(missing)}")
        remaining = fr.get("remaining_placeholders", [])
        if remaining:
            issues.append(f"残留占位符：{', '.join(remaining)}。")
            suggestions.append("重新填充残留占位符字段")
        if "teaching_process" not in fr.get("filled_fields", []):
            issues.append("teaching_process（主要教学内容）未写入 Word。")
            suggestions.append("强制使用 template_analysis 中 next_row_cell target 重新写入")

    # Check output path
    output_name = (state.export_result or {}).get("output_name")
    if not output_name:
        issues.append("Word 输出文件未生成（output_path 不存在）。")
        suggestions.append("重新执行 export_docx")

    if not issues:
        issues.append("未检测到明确失败原因。")
        suggestions.append("检查原始错误日志")

    return {
        "issues": issues,
        "suggestions": suggestions,
        "repairable": len(suggestions) > 0,
    }


def repair_state(state: AgentRunState) -> AgentRunState:
    """Attempt to repair a failed state. Only runs once.

    Side effects on `state`: updates status to 'repairing' during attempt,
    then to either 'completed' or 'failed'.
    """
    if state.retry_count >= state.max_retries:
        state.status = "failed"
        state.errors.append("已达到最大修复次数，无法自动修复。")
        return state

    state.status = "repairing"
    state.retry_count += 1

    diagnosis = diagnose_failure(state)
    state.teacher_report = diagnosis

    fields = state.fields or {}

    # Repair: fill missing fields with fallback
    from ..lesson_generator import _local_fallback_fields
    dynamic_fields = list(fields.keys()) if fields else []
    fallback = _local_fallback_fields(
        subject=str(fields.get("subject") or state.task.get("subject", "")),
        grade=str(fields.get("grade") or state.task.get("grade", "")),
        title=str(fields.get("lesson_title") or state.task.get("title", "未命名")),
        material=str(state.task.get("material", "")),
        class_hour=str(fields.get("class_hour") or state.task.get("class_hour", "1课时")),
        dynamic_fields=dynamic_fields or [],
    )
    for k, v in fallback.items():
        if k not in fields or not str(fields.get(k, "")).strip():
            fields[k] = v
    state.fields = fields

    # Check if any real repair happened
    non_empty = sum(1 for v in fields.values() if str(v or "").strip())
    if non_empty > 0:
        state.warnings.append("已通过 local fallback 修复空字段，建议老师预览后再导出。")
        state.status = "fields_generated"  # ready to retry export
        state.next_action = "export_docx"
    else:
        state.status = "failed"
        state.errors.append("修复失败：无法生成有效的教案内容。")

    return state
