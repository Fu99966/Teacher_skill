from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Mapping

from ..lesson_generator import (
    DEFAULT_CLASS_TYPE,
    DEFAULT_GENERATION_DEPTH,
    DEFAULT_STUDENT_LEVEL,
    DEFAULT_TEACHING_STYLE,
)


SUBJECTS = (
    "语文",
    "数学",
    "英语",
    "物理",
    "化学",
    "生物",
    "科学",
    "历史",
    "地理",
    "道德与法治",
    "政治",
    "音乐",
    "美术",
    "体育",
    "信息技术",
    "劳动",
)

GRADE_PATTERN = re.compile(
    r"(小学|初中|高中|大学|本科|专科)?[一二三四五六七八九十\d]+年级|"
    r"高[一二三\d]|初[一二三\d]|大[一二三四\d]"
)


@dataclass
class AgentTask:
    raw_request: str
    task_type: str
    subject: str
    grade: str
    title: str
    class_hour: str
    class_type: str
    teaching_style: str
    student_level: str
    generation_depth: str
    missing_fields: list[str]
    confidence: float
    notes: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def route_task(text: str, defaults: Mapping[str, str] | None = None) -> AgentTask:
    defaults = defaults or {}
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    task_type = _infer_task_type(normalized)
    subject = _first(defaults.get("subject"), _extract_subject(normalized))
    grade = _first(defaults.get("grade"), _extract_grade(normalized))
    title = _first(defaults.get("title"), _extract_title(normalized))
    class_hour = _first(defaults.get("class_hour"), _extract_class_hour(normalized), "1课时")
    class_type = _first(defaults.get("class_type"), _extract_class_type(normalized), DEFAULT_CLASS_TYPE)
    teaching_style = _first(defaults.get("teaching_style"), _extract_teaching_style(normalized), DEFAULT_TEACHING_STYLE)
    student_level = _first(defaults.get("student_level"), _extract_student_level(normalized), DEFAULT_STUDENT_LEVEL)
    generation_depth = _first(defaults.get("generation_depth"), _extract_generation_depth(normalized), DEFAULT_GENERATION_DEPTH)

    missing = []
    if task_type != "lesson_plan":
        missing.append("task_type")
    for key, value in (("subject", subject), ("grade", grade), ("title", title)):
        if not value:
            missing.append(key)

    confidence = 0.42
    if task_type == "lesson_plan":
        confidence += 0.22
    confidence += 0.1 * len([value for value in (subject, grade, title) if value])
    confidence = min(confidence, 0.96)

    notes = []
    if missing:
        notes.append("需要补齐关键信息后才能稳定执行。")
    else:
        notes.append("已识别为教案生成任务，可调用 V5 工作流。")

    return AgentTask(
        raw_request=normalized,
        task_type=task_type,
        subject=subject,
        grade=grade,
        title=title,
        class_hour=class_hour,
        class_type=class_type,
        teaching_style=teaching_style,
        student_level=student_level,
        generation_depth=generation_depth,
        missing_fields=missing,
        confidence=round(confidence, 2),
        notes=notes,
    )


def _first(*values: str | None) -> str:
    for value in values:
        text = (value or "").strip()
        if text:
            return text
    return ""


def _infer_task_type(text: str) -> str:
    if any(keyword in text for keyword in ("教案", "备课", "教学设计", "课时设计")):
        return "lesson_plan"
    if any(keyword in text for keyword in ("学习单", "导学案", "练习单")):
        return "worksheet"
    if any(keyword in text for keyword in ("PPT", "课件")):
        return "ppt_outline"
    return "lesson_plan" if text else "unknown"


def _extract_subject(text: str) -> str:
    for subject in SUBJECTS:
        if subject in text:
            return subject
    return ""


def _extract_grade(text: str) -> str:
    match = GRADE_PATTERN.search(text)
    return match.group(0) if match else ""


def _extract_title(text: str) -> str:
    match = re.search(r"《([^》]+)》", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"[\"“]([^\"”]+)[\"”]", text)
    if match:
        return match.group(1).strip()
    match = re.search(r"(?:课题|主题|内容|关于)\s*[:：]?\s*([\u4e00-\u9fa5A-Za-z0-9·\-]{2,30})", text)
    return match.group(1).strip() if match else ""


def _extract_class_hour(text: str) -> str:
    match = re.search(r"(\d+|[一二三四五六七八九十]+)\s*课时", text)
    return match.group(0) if match else ""


def _extract_class_type(text: str) -> str:
    if "复习" in text:
        return "复习课"
    if "讲评" in text or "习题" in text:
        return "讲评课 / 习题课"
    if "实验" in text or "探究" in text:
        return "探究/实验课"
    if "活动" in text or "拓展" in text:
        return "活动课 / 拓展课"
    if "新授" in text:
        return "新授课"
    return ""


def _extract_teaching_style(text: str) -> str:
    if "BOPPPS" in text.upper() or "参与式" in text:
        return "BOPPPS参与式教学"
    if "5E" in text.upper() or "探究" in text:
        return "5E探究模型"
    if "PBL" in text.upper() or "项目" in text:
        return "项目驱动(PBL)"
    if "游戏" in text:
        return "游戏化教学"
    return ""


def _extract_student_level(text: str) -> str:
    if any(keyword in text for keyword in ("基础薄弱", "补弱", "学困")):
        return "基础薄弱 / 补弱导向"
    if any(keyword in text for keyword in ("培优", "学有余力", "拔高")):
        return "学有余力 / 培优导向"
    return ""


def _extract_generation_depth(text: str) -> str:
    if "精简" in text or "简短" in text:
        return "精简"
    if "深度" in text or "详细" in text or "公开课" in text:
        return "深度"
    return ""
