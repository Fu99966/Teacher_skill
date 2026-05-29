from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .deepseek_client import chat_json, is_deepseek_configured
from .lesson_generator import JSON_FIELD_NAMES, coerce_dynamic_fields


@dataclass
class ReviewReport:
    reviewer: str
    score: int
    summary: str
    issues: list[str]
    improvements: list[str]
    backend: str
    revision_applied: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _field_text(fields: dict[str, str], *names: str) -> str:
    for name in names:
        value = str(fields.get(name) or "").strip()
        if value:
            return value
    return ""


def _is_non_empty_revision_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(str(value).strip())


def _revision_text(value) -> str:
    if isinstance(value, str):
        return value.replace("{{", "").replace("}}", "").strip()
    if isinstance(value, (list, tuple)):
        return "\n".join(_revision_text(item) for item in value if _is_non_empty_revision_value(item)).strip()
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).strip()


def merge_revision_preserving_original(
    original: dict[str, str],
    revised: dict[str, object],
    allowed_fields: list[str],
) -> dict[str, str]:
    allowed = list(dict.fromkeys(str(field) for field in allowed_fields))
    merged = {field: str(original.get(field) or "") for field in allowed}
    if not isinstance(revised, dict):
        return merged

    for field in allowed:
        if field not in revised:
            continue
        value = revised[field]
        if not _is_non_empty_revision_value(value):
            continue
        merged[field] = _revision_text(value)
    return merged


def _local_review(fields: dict[str, str], context: dict) -> ReviewReport:
    process = _field_text(fields, "teaching_process", "process", "教学过程")
    goals = _field_text(fields, "teaching_goals", "goals", "教学目标")
    homework = _field_text(fields, "homework", "作业", "课后任务")
    issues: list[str] = []
    improvements: list[str] = []

    if process and ("教师活动" not in process or "学生活动" not in process):
        issues.append("教学过程中的师生活动边界还可以更清晰。")
        improvements.append("为核心环节补充教师活动和学生活动。")
    if process and len(process) < 360:
        issues.append("教学过程略简，课堂推进证据不足。")
        improvements.append("增加探究、评价或迁移任务，让流程更可执行。")
    if homework and ("基础" not in homework or "提升" not in homework):
        issues.append("作业分层还不够稳定。")
        improvements.append("保持基础题、提升题、拓展题三层结构。")
    if goals and all(keyword not in goals for keyword in ("核心素养", "情感", "价值")):
        issues.append("教学目标可进一步对齐核心素养或育人价值。")
        improvements.append("在目标中补充素养表现或情感态度维度。")

    if not issues:
        issues.append("整体结构完整，可在课堂评价方式上继续精细化。")
        improvements.append("补充可观察的课堂评价证据，例如出口卡、同伴互评或表现性任务。")

    class_type = context.get("class_type", "课型")
    teaching_style = context.get("teaching_style", "教学法")
    score = max(78, 92 - max(0, len(issues) - 1) * 4)
    return ReviewReport(
        reviewer="教研组长 Agent",
        score=score,
        summary=f"已按“{class_type} + {teaching_style}”进行预审，文档主体可用，建议继续强化课堂证据和评价闭环。",
        issues=issues[:4],
        improvements=improvements[:4],
        backend="local",
    )


def review_lesson_quality(fields: dict[str, str], context: dict) -> ReviewReport:
    if not is_deepseek_configured():
        return _local_review(fields, context)

    prompt = f"""你是教研组长/特级教师审阅 Agent。请审阅下面的教学文档初稿，指出是否符合课型、学段特点、教学法和课堂落地要求。
上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}

教学文档初稿：
{json.dumps(fields, ensure_ascii=False, indent=2)}

只输出合法 JSON，字段必须为：
{{
  "score": 0-100 的整数,
  "summary": "一句话总体评价",
  "issues": ["问题1", "问题2"],
  "improvements": ["建议1", "建议2"]
}}"""

    try:
        data = chat_json(
            prompt,
            system="你是严谨的教研审阅引擎，只输出合法 JSON，不输出 Markdown。",
            temperature=0.35,
            max_tokens=2200,
        )
        score = int(data.get("score") or 86)
        issues = [str(item) for item in data.get("issues", []) if str(item).strip()]
        improvements = [str(item) for item in data.get("improvements", []) if str(item).strip()]
        return ReviewReport(
            reviewer="教研组长 Agent",
            score=max(0, min(100, score)),
            summary=str(data.get("summary") or "已完成教研审阅。"),
            issues=issues[:5] or ["未发现明显结构问题。"],
            improvements=improvements[:5] or ["继续优化课堂评价证据。"],
            backend="deepseek",
        )
    except Exception:
        report = _local_review(fields, context)
        report.backend = "local_fallback"
        return report


def _first_existing_field(fields: dict[str, str], candidates: list[str]) -> str | None:
    for field in candidates:
        if field in fields:
            return field
    return None


def _apply_local_revision(fields: dict[str, str], report: ReviewReport) -> dict[str, str]:
    revised = dict(fields)
    suggestion_text = "；".join(report.improvements[:2])
    reflection_field = _first_existing_field(revised, ["reflection", "teaching_reflection", "review_notes"])
    process_field = _first_existing_field(revised, ["teaching_process", "process", "class_process"])

    if suggestion_text:
        if reflection_field:
            current = revised.get(reflection_field, "").rstrip()
            if suggestion_text not in current:
                revised[reflection_field] = (
                    current
                    + f"\n教研预审调整：课后重点观察“{suggestion_text}”是否真正改善学生学习表现。"
                ).strip()
        elif "review_notes" in revised:
            revised["review_notes"] = suggestion_text

    if process_field and "出口卡" not in revised.get(process_field, "") and report.improvements:
        revised[process_field] = (
            revised.get(process_field, "").rstrip()
            + "\n\n教研优化环节：课堂结束前设置 2 分钟出口卡，学生写下一个已掌握要点和一个仍需追问的问题，教师据此调整后续教学。"
        ).strip()

    report.revision_applied = True
    return revised


def revise_lesson_after_review(
    fields: dict[str, str],
    report: ReviewReport,
    context: dict,
    dynamic_fields: list[str] | None = None,
) -> tuple[dict[str, str], str]:
    allowed_fields = dynamic_fields or list(fields.keys()) or JSON_FIELD_NAMES
    if not is_deepseek_configured():
        return _apply_local_revision(fields, report), "local"

    prompt = f"""你是执教老师 Agent。请根据教研组长审阅意见，对教学文档初稿进行二次修订。
要求：
1. 只输出一个合法 JSON 对象。
2. JSON Key 必须严格且仅包含这些字段：{json.dumps(allowed_fields, ensure_ascii=False)}
3. 不要输出 Markdown，不要输出解释，不要出现模板占位符。
4. 保留原文档的课题、学科、年级和课时，不要改变 Word 模板结构。

上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}

审阅意见：
{json.dumps(report.to_dict(), ensure_ascii=False, indent=2)}

教学文档初稿：
{json.dumps(fields, ensure_ascii=False, indent=2)}
"""
    try:
        data = chat_json(
            prompt,
            system="你是教师教学文档修订引擎，只输出合法 JSON，不输出 Markdown。",
            temperature=0.55,
            max_tokens=7200,
        )
        report.revision_applied = True
        return merge_revision_preserving_original(fields, data if isinstance(data, dict) else {}, allowed_fields), "deepseek"
    except Exception:
        return _apply_local_revision(fields, report), "local_fallback"
