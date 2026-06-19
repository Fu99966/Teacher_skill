from __future__ import annotations

from typing import Any

from .state import AgentRunState


def diagnose_failure(state: AgentRunState) -> dict[str, Any]:
    issues: list[str] = []
    suggestions: list[str] = []
    fields = state.fields or {}
    fill_report = (state.export_result or {}).get("fill_report", {}) if state.export_result else {}
    output_quality = (state.export_result or {}).get("output_quality_report", {}) if state.export_result else {}
    evaluation = state.evaluation_report or {}

    if not fields:
        issues.append("fields 为空：未生成任何教案字段。")
        suggestions.append("使用本地 fallback 重新补齐字段。")
    else:
        empty = [key for key, value in fields.items() if not str(value or "").strip()]
        if empty:
            issues.append("存在空字段：" + "、".join(empty[:8]))
            suggestions.append("用本地 fallback 补齐空字段。")

    if fill_report:
        if int(fill_report.get("filled_non_empty_count") or 0) == 0:
            issues.append("filled_non_empty_count=0：Word 未写入任何非空字段，存在空白模板风险。")
            suggestions.append("阻断成功状态，重新填充或提示模板字段问题。")
        if fill_report.get("remaining_placeholders"):
            issues.append("Word 中仍有占位符残留。")
            suggestions.append("按残留占位符补齐同名字段后重新导出。")
        fwc = fill_report.get("field_write_counts", {})
        if fwc.get("teaching_process", 0) == 0:
            issues.append("主要教学内容未写入 Word。")
        if fwc.get("teaching_method", 0) == 0:
            issues.append("教学方法的运用未写入 Word。")

    if evaluation and not evaluation.get("passed", True):
        issues.append(str(evaluation.get("summary") or "交付检查未通过。"))

    if output_quality and not output_quality.get("passed", True):
        for error in output_quality.get("errors") or []:
            message = str(error).strip()
            if message and message not in issues:
                issues.append(message)
        suggestions.append("已重新读取最终 Word，请按实际交付文档问题修复后重新导出。")

    if not issues:
        issues.append("未检测到明确失败原因。")
    if not suggestions:
        suggestions.append("重新读取输出 Word 并检查模板字段定位。")
    return {"issues": issues, "suggestions": suggestions, "repairable": True}


def repair_state(state: AgentRunState) -> AgentRunState:
    if state.retry_count >= state.max_retries:
        state.status = "failed"
        state.errors.append("已达到最大自动修复次数，无法继续修复。")
        return state

    state.status = "repairing"
    state.retry_count += 1
    diagnosis = diagnose_failure(state)
    state.teacher_report = diagnosis

    fields = dict(state.fields or {})
    task = state.task or {}

    from ..lesson_generator import (
        _local_fallback_fields,
        is_generation_request_text,
        normalize_lesson_field_aliases,
        refine_lesson_field,
        sanitize_lesson_title,
        sanitize_material_hint,
    )

    fields = normalize_lesson_field_aliases(fields, str(task.get("raw_text") or task.get("agent_request") or ""))
    title = sanitize_lesson_title(
        str(fields.get("lesson_title") or task.get("title") or ""),
        str(task.get("raw_text") or task.get("agent_request") or ""),
        str(task.get("title") or ""),
    )
    if title:
        fields["lesson_title"] = title

    material = sanitize_material_hint(str(task.get("material") or ""), str(task.get("raw_text") or ""), title)
    dynamic_fields = list((state.template_analysis or {}).get("mapped_fields") or fields.keys())
    fallback = _local_fallback_fields(
        subject=str(fields.get("subject") or task.get("subject") or ""),
        grade=str(fields.get("grade") or task.get("grade") or ""),
        title=title or str(task.get("title") or "未命名课题"),
        material=material,
        class_hour=str(fields.get("class_hour") or task.get("class_hour") or "1课时"),
        dynamic_fields=dynamic_fields,
        class_type=str(fields.get("class_type") or task.get("class_type") or ""),
    )

    for key in dynamic_fields:
        if not str(fields.get(key) or "").strip():
            fields[key] = fallback.get(key, "")

    if not str(fields.get("teaching_method") or "").strip() and str(fields.get("teaching_process") or "").strip():
        fields["teaching_method"] = refine_lesson_field(
            "teaching_method",
            str(fields.get("teaching_process") or ""),
            "derive_from_process",
            title,
        )

    raw_request = str(task.get("raw_text") or task.get("agent_request") or "").strip()
    for key in dynamic_fields:
        value = str(fields.get(key) or "")
        if not value:
            continue
        cleaned = value.replace(raw_request, "").strip() if raw_request else value
        cleaned = "\n".join(
            line for line in cleaned.splitlines()
            if not is_generation_request_text(line)
        ).strip()
        if cleaned != value:
            fields[key] = cleaned or fallback.get(key, value)

    state.fields = fields
    if any(str(value or "").strip() for value in fields.values()):
        state.warnings.append("已执行自动修复：补齐空字段、派生教学方法并清理 prompt 泄漏风险。")
        state.status = "fields_generated"
        state.next_action = "export_docx"
    else:
        state.status = "failed"
        state.errors.append("自动修复失败：仍无法生成有效教案字段。")
    return state
