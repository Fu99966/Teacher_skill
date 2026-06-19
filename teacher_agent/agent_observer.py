from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


FIELD_LABELS: dict[str, str] = {
    "teaching_date": "授课日期",
    "class_name": "授课班级",
    "lesson_title": "课题",
    "subject": "学科",
    "grade": "班级/年级",
    "class_type": "授课类型",
    "class_hour": "课时数",
    "teaching_environment": "对教学环境的要求",
    "teaching_goals": "教学目的",
    "key_points": "教学重点",
    "difficult_points": "教学难点",
    "teaching_key_difficult": "重点难点",
    "teaching_preparation": "教学准备",
    "blackboard_design": "板书设计",
    "teaching_aids": "教具挂图",
    "teaching_process": "主要教学内容",
    "teaching_method": "教学方法的运用",
    "homework": "作业",
    "reflection": "课后小记",
}


@dataclass
class TeacherDiagnosticReport:
    status: str
    summary: str
    recognized_fields: list[dict[str, Any]] = field(default_factory=list)
    written_fields: list[dict[str, Any]] = field(default_factory=list)
    unwritten_fields: list[dict[str, Any]] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    template_profile: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [f"# 生成诊断报告", "", f"状态：{self.status}", f"摘要：{self.summary}", ""]
        lines.append("## 已识别字段")
        for item in self.recognized_fields:
            lines.append(f"- {item['label']}（{item['field']}）")
        lines.append("")
        lines.append("## 已写入字段")
        if self.written_fields:
            for item in self.written_fields:
                lines.append(f"- {item['label']}：写入 {item['written_count']} 处")
        else:
            lines.append("- 无")
        lines.append("")
        lines.append("## 未写入字段")
        if self.unwritten_fields:
            for item in self.unwritten_fields:
                lines.append(f"- {item['label']}：{item['reason']}")
        else:
            lines.append("- 无")
        if self.reasons:
            lines.extend(["", "## 原因"])
            lines.extend(f"- {reason}" for reason in self.reasons)
        if self.next_actions:
            lines.extend(["", "## 建议"])
            lines.extend(f"- {action}" for action in self.next_actions)
        return "\n".join(lines)


def build_teacher_diagnostic_report(
    *,
    template_analysis: dict[str, Any] | None,
    fill_report: dict[str, Any] | None,
    evaluation_report: dict[str, Any] | None,
    fields: dict[str, Any] | None,
    output_quality_report: dict[str, Any] | None = None,
    template_profile: dict[str, Any] | None = None,
) -> TeacherDiagnosticReport:
    analysis = template_analysis or {}
    fill = fill_report or {}
    evaluation = evaluation_report or {}
    output_quality = output_quality_report or {}
    field_values = fields or {}

    mapped_fields = list(analysis.get("mapped_fields") or [])
    write_counts = dict(fill.get("field_write_counts") or {})
    missing_fields = set(fill.get("missing_fields") or [])
    empty_fields = set(fill.get("empty_fields") or []) | set(fill.get("skipped_empty_fields") or [])
    remaining_placeholders = list(fill.get("remaining_placeholders") or [])
    errors = list(fill.get("errors") or [])
    warnings = list(fill.get("warnings") or [])

    recognized = [_field_item(field) for field in mapped_fields]
    written = []
    unwritten = []

    for field in mapped_fields:
        count = int(write_counts.get(field) or 0)
        value_present = bool(str(field_values.get(field) or "").strip())
        if count > 0:
            item = _field_item(field)
            item["written_count"] = count
            written.append(item)
            continue
        reason = "模板中识别到字段，但没有写入目标位置"
        if field in missing_fields:
            reason = "生成结果缺少该字段"
        elif field in empty_fields or not value_present:
            reason = "字段内容为空，系统为避免清空模板而跳过写入"
        item = _field_item(field)
        item["reason"] = reason
        unwritten.append(item)

    reasons: list[str] = []
    if errors:
        reasons.extend(str(item) for item in errors)
    if warnings:
        reasons.extend(str(item) for item in warnings[:5])
    if remaining_placeholders:
        reasons.append("Word 中仍有占位符未替换：" + "、".join(remaining_placeholders[:8]))
    if evaluation and not evaluation.get("passed", True):
        reasons.append(str(evaluation.get("summary") or "自动交付检查未通过"))
    if output_quality and not output_quality.get("passed", True):
        reasons.extend(str(item) for item in (output_quality.get("errors") or [])[:6])
    if not mapped_fields:
        reasons.append("模板中没有识别到可填字段")

    next_actions: list[str] = []
    if not mapped_fields:
        next_actions.append("在模板中加入 {{字段名}} 占位符，或使用常见表格标签如“教学目的”“主要教学内容”。")
    if unwritten:
        next_actions.append("检查未写入字段的模板位置；必要时改用占位符模板或在预览页补齐字段。")
    if remaining_placeholders:
        next_actions.append("确认占位符名称与生成字段名称完全一致。")
    if output_quality and not output_quality.get("passed", True):
        next_actions.append("根据最终 Word 质量检查提示修复内容后重新导出；系统会优先尝试自动修复可恢复问题。")
    if not next_actions:
        next_actions.append("可下载 Word；如学校格式有细节要求，可在 Word 中做最终微调。")

    if errors or (evaluation and not evaluation.get("passed", True)) or (output_quality and not output_quality.get("passed", True)):
        status = "failed"
    elif unwritten or warnings or remaining_placeholders:
        status = "needs_review"
    else:
        status = "passed"

    summary = _summary(status, mapped_fields, written, unwritten)
    return TeacherDiagnosticReport(
        status=status,
        summary=summary,
        recognized_fields=recognized,
        written_fields=written,
        unwritten_fields=unwritten,
        reasons=reasons,
        next_actions=next_actions,
        template_profile=_profile_summary(template_profile),
    )


def _field_item(field: str) -> dict[str, Any]:
    return {"field": field, "label": FIELD_LABELS.get(field, field)}


def _summary(status: str, mapped_fields: list[str], written: list[dict[str, Any]], unwritten: list[dict[str, Any]]) -> str:
    if status == "passed":
        return f"已识别 {len(mapped_fields)} 个模板字段，并成功写入 {len(written)} 个字段。"
    if status == "failed":
        return f"生成或写入存在阻断问题：识别 {len(mapped_fields)} 个字段，成功写入 {len(written)} 个字段。"
    return f"已生成 Word，但仍需复核：识别 {len(mapped_fields)} 个字段，成功写入 {len(written)} 个字段，{len(unwritten)} 个字段未写入。"


def _profile_summary(profile: dict[str, Any] | None) -> dict[str, Any] | None:
    if not profile:
        return None
    return {
        "template_id": profile.get("template_id"),
        "profile_hit": bool(profile.get("profile_hit")),
        "mapped_field_count": len(profile.get("mapped_fields") or []),
        "repeat_fill_mode": profile.get("repeat_fill_mode") or profile.get("duplicate_table_policy"),
        "last_successful_fill": profile.get("last_successful_fill") or {},
    }
