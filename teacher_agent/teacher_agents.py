from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .deepseek_client import chat_json, is_deepseek_configured
from .lesson_generator import JSON_FIELD_NAMES, LessonFields, coerce_lesson_fields


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


def _local_review(fields: LessonFields, context: dict) -> ReviewReport:
    data = fields.to_dict()
    process = data.get("teaching_process", "")
    goals = data.get("teaching_goals", "")
    homework = data.get("homework", "")
    issues: list[str] = []
    improvements: list[str] = []

    if "教师活动" not in process or "学生活动" not in process:
        issues.append("教学过程中的师生活动边界还可以更清晰。")
        improvements.append("为每个核心环节补充教师活动和学生活动。")
    if len(process) < 360:
        issues.append("教学过程略简，课堂推进证据不足。")
        improvements.append("增加探究、评价或迁移任务，让流程更可执行。")
    if "基础" not in homework or "提升" not in homework:
        issues.append("作业分层还不够稳定。")
        improvements.append("保持基础题、提升题、拓展题三层结构。")
    if "核心素养" not in goals and "情感" not in goals and "价值" not in goals:
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
        summary=f"已按“{class_type} + {teaching_style}”进行预审，教案主体可用，建议继续强化课堂证据和评价闭环。",
        issues=issues[:4],
        improvements=improvements[:4],
        backend="local",
    )


def review_lesson_quality(fields: LessonFields, context: dict) -> ReviewReport:
    if not is_deepseek_configured():
        return _local_review(fields, context)

    prompt = f"""你是教研组长/特级教师审阅 Agent。请审阅下面的教案初稿，指出是否符合课型、学段特点、教学法和课堂落地要求。

上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}

教案初稿：
{json.dumps(fields.to_dict(), ensure_ascii=False, indent=2)}

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


def _apply_local_revision(fields: LessonFields, report: ReviewReport) -> LessonFields:
    data = fields.to_dict()
    suggestion_text = "；".join(report.improvements[:2])
    if suggestion_text and suggestion_text not in data["reflection"]:
        data["reflection"] = (
            data["reflection"].rstrip()
            + f"\n教研预审调整：课后重点观察“{suggestion_text}”是否真正改善学生学习表现。"
        )
    if "出口卡" not in data["teaching_process"] and report.improvements:
        data["teaching_process"] = (
            data["teaching_process"].rstrip()
            + "\n\n教研优化环节：课堂结束前设置 2 分钟出口卡，学生写下一个已掌握要点和一个仍需追问的问题，教师据此调整后续教学。"
        )
    revised = LessonFields(**data)
    report.revision_applied = True
    return revised


def revise_lesson_after_review(fields: LessonFields, report: ReviewReport, context: dict) -> tuple[LessonFields, str]:
    if not is_deepseek_configured():
        return _apply_local_revision(fields, report), "local"

    prompt = f"""你是执教老师 Agent。请根据教研组长审阅意见，对教案初稿进行二次修订。

要求：
1. 只输出一个合法 JSON 对象。
2. JSON Key 必须严格使用这些字段：{json.dumps(JSON_FIELD_NAMES, ensure_ascii=False)}
3. 不要输出 Markdown，不要输出解释，不要出现模板占位符。
4. 保留原教案的课题、学科、年级和课时，不要改变 Word 模板结构。

上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}

审阅意见：
{json.dumps(report.to_dict(), ensure_ascii=False, indent=2)}

教案初稿：
{json.dumps(fields.to_dict(), ensure_ascii=False, indent=2)}
"""
    try:
        data = chat_json(
            prompt,
            system="你是教师教案修订引擎，只输出合法 JSON，不输出 Markdown。",
            temperature=0.55,
            max_tokens=7200,
        )
        report.revision_applied = True
        return coerce_lesson_fields(data, fields), "deepseek"
    except Exception:
        return _apply_local_revision(fields, report), "local_fallback"
