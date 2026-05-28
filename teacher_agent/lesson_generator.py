from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .deepseek_client import DeepSeekError, chat_json, check_deepseek_health, is_deepseek_configured, load_local_env


JSON_FIELD_NAMES = [
    "lesson_title",
    "subject",
    "grade",
    "class_hour",
    "teaching_goals",
    "key_points",
    "difficult_points",
    "teaching_preparation",
    "teaching_process",
    "blackboard_design",
    "homework",
    "reflection",
]

DEFAULT_CLASS_TYPE = "新授课"
DEFAULT_TEACHING_STYLE = "常规启发式"
DEFAULT_STUDENT_LEVEL = "常规混合水平"
DEFAULT_GENERATION_DEPTH = "标准"

REFINE_ACTIONS = {
    "more_vivid": "更像公开课",
    "deepen_inquiry": "深化探究",
    "simplify": "更适合基础班",
    "more_interaction": "增加课堂互动",
    "shorten": "压缩到40分钟",
    "clean_blackboard": "板书更简洁",
}


class LessonGenerationError(RuntimeError):
    """Raised when a generated response cannot be parsed into template fields."""


def infer_school_stage(grade: str) -> str:
    text = grade.strip()
    higher_markers = [
        "大学",
        "本科",
        "专科",
        "高职",
        "研究生",
        "硕士",
        "博士",
        "大一",
        "大二",
        "大三",
        "大四",
    ]
    secondary_markers = [
        "初中",
        "高中",
        "中学",
        "初一",
        "初二",
        "初三",
        "高一",
        "高二",
        "高三",
        "七年级",
        "八年级",
        "九年级",
    ]
    primary_markers = ["小学", "一年级", "二年级", "三年级", "四年级", "五年级", "六年级"]

    if any(marker in text for marker in higher_markers):
        return "higher"
    if any(marker in text for marker in secondary_markers):
        return "secondary"
    if any(marker in text for marker in primary_markers):
        return "primary"

    match = re.search(r"(\d+)", text)
    if match:
        number = int(match.group(1))
        if 1 <= number <= 6:
            return "primary"
        if 7 <= number <= 12:
            return "secondary"

    return "secondary"


def _stage_name(stage: str) -> str:
    return {
        "primary": "小学阶段",
        "secondary": "中学阶段",
        "higher": "大学阶段",
    }.get(stage, "中学阶段")


def _normalize_dynamic_fields(dynamic_fields: list[str] | None) -> list[str]:
    result: list[str] = []
    for raw_field in dynamic_fields or JSON_FIELD_NAMES:
        field = str(raw_field or "").strip()
        if not field:
            continue
        field = field.replace("{{", "").replace("}}", "").strip()
        field = re.sub(r"[^a-zA-Z0-9_\-\.]", "", field)
        if field and field not in result:
            result.append(field)
    return result or list(JSON_FIELD_NAMES)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    elif isinstance(value, (list, tuple)):
        text = "\n".join(_clean_text(item) for item in value)
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        text = str(value)
    return text.replace("{{", "").replace("}}", "").strip()


def coerce_dynamic_fields(data: dict[str, Any] | dict, dynamic_fields: list[str] | None) -> dict[str, str]:
    fields = _normalize_dynamic_fields(dynamic_fields)
    source = data if isinstance(data, dict) else {}
    return {field: _clean_text(source.get(field)) for field in fields}


def build_lesson_prompt(
    subject: str,
    grade: str,
    title: str,
    material: str,
    class_hour: str = "1课时",
    class_type: str = DEFAULT_CLASS_TYPE,
    teaching_style: str = DEFAULT_TEACHING_STYLE,
    student_level: str = DEFAULT_STUDENT_LEVEL,
    generation_depth: str = DEFAULT_GENERATION_DEPTH,
    dynamic_fields: list[str] | None = None,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> str:
    fields = _normalize_dynamic_fields(dynamic_fields)
    fields_json = json.dumps(fields, ensure_ascii=False)
    stage = _stage_name(infer_school_stage(grade))
    material_text = material.strip() or "用户没有提供教材内容，请生成通用版教案，并避免编造具体教材页码。"
    creative = creative_mode.strip() or "常规稳妥"

    anti_repetition_block = ""
    if anti_repetition_context.strip():
        anti_repetition_block = f"""
# 历史反重复要求
以下是近期相似教案摘要。请避免复用其中的导入方式、活动顺序、作业表达和板书结构：
{anti_repetition_context.strip()}
"""

    few_shot_block = ""
    if few_shot_examples.strip():
        few_shot_block = f"""
# 优秀样例参考
以下样例只用于学习质量、颗粒度和课堂活动设计方式，不能照抄措辞：
{few_shot_examples.strip()}
"""

    return f"""
# 角色设定
你是由小学高级教师、中学特级教师、大学资深教授组成的“全学段特级教师团队”。你熟悉教育心理学、认知发展规律、课程标准和课堂落地写法。

# 核心任务
根据用户提供的课程信息，为 Word 模板自动填充生成教学文档内容。
你必须输出一个纯 JSON 对象，JSON 的 Key 必须严格且仅包含以下列表中的字段：
{fields_json}

请根据字段的字面意思生成对应的教学内容。字段可能来自学校 Word 模板，不一定是标准教案字段；例如 warm_up、safety_rules、core_training、assessment 等，都要按字段语义生成可直接填入模板的文本。

# 学段差异化原则
当前识别学段：{stage}
1. 小学阶段：激发兴趣、习惯养成、直观感知，多用游戏化教学、情境导入、实物展示、小组互助。
2. 中学阶段：知识体系构建、逻辑思维培养、考点对齐，强调自主探究、典型例题、变式训练和迁移应用。
3. 大学阶段：学术视野、专业前沿、独立研究与实践应用，采用研讨式、案例教学或项目驱动。

# 动态生成要求
1. 课型适配：本次课型为「{class_type}」，内容必须符合该课型的典型特征。
2. 教学法/风格：采用「{teaching_style}」组织课堂。
3. 学情自适应：目标学生群体为「{student_level}」，在难点突破、教师话术、课堂活动和作业设计中体现针对性。
4. 生成深度：输出深度为「{generation_depth}」。
5. 风格控制：本次生成风格为「{creative}」。
6. 模板优先：不要新增模板字段之外的 Key；不要遗漏给定字段；不要输出模板占位符。

{anti_repetition_block}
{few_shot_block}

# 严格输出限制
1. 绝对不要输出 Markdown，也不要输出解释性前言或后语。
2. 唯一输出必须是一个合法 JSON 对象，可直接被 JSON.parse() 解析。
3. 不得在内容中加入 "{{" 或 "}}"。
4. JSON Key 必须严格且仅包含：{fields_json}

# 用户输入
学科：{subject}
年级：{grade}
课题：{title}
课时：{class_hour}
课型：{class_type}
教学法/风格：{teaching_style}
学生层次：{student_level}
生成深度：{generation_depth}
教材内容/知识点：
{material_text}
""".strip()


def check_generation_health(probe: bool = False) -> Any:
    return check_deepseek_health(probe=probe)


def draft_lesson_fields(
    subject: str,
    grade: str,
    title: str,
    material: str,
    class_hour: str = "1课时",
    class_type: str = DEFAULT_CLASS_TYPE,
    teaching_style: str = DEFAULT_TEACHING_STYLE,
    student_level: str = DEFAULT_STUDENT_LEVEL,
    generation_depth: str = DEFAULT_GENERATION_DEPTH,
    dynamic_fields: list[str] | None = None,
    strict_ai: bool = False,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> dict[str, str]:
    fields = _normalize_dynamic_fields(dynamic_fields)
    prompt = build_lesson_prompt(
        subject=subject,
        grade=grade,
        title=title,
        material=material,
        class_hour=class_hour,
        class_type=class_type,
        teaching_style=teaching_style,
        student_level=student_level,
        generation_depth=generation_depth,
        dynamic_fields=fields,
        creative_mode=creative_mode,
        anti_repetition_context=anti_repetition_context,
        few_shot_examples=few_shot_examples,
    )
    if not is_deepseek_configured():
        raise DeepSeekError(
            "DEEPSEEK_API_KEY is not configured",
            error_type="not_configured",
            user_message="未配置 DEEPSEEK_API_KEY，无法调用 DeepSeek 生成。请先在 .env 中填写。",
        )

    raw_data = chat_json(
        prompt,
        system="你是教育文档 JSON 生成引擎。只输出合法 JSON，不输出 Markdown，不输出解释。",
        temperature=0.78,
        max_tokens=7600,
    )
    if not isinstance(raw_data, dict):
        raise LessonGenerationError("DeepSeek 返回 JSON 不是对象，无法填充 Word 模板。")
    return coerce_dynamic_fields(raw_data, fields)


def draft_lesson_fields_with_source(
    subject: str,
    grade: str,
    title: str,
    material: str,
    class_hour: str = "1课时",
    class_type: str = DEFAULT_CLASS_TYPE,
    teaching_style: str = DEFAULT_TEACHING_STYLE,
    student_level: str = DEFAULT_STUDENT_LEVEL,
    generation_depth: str = DEFAULT_GENERATION_DEPTH,
    dynamic_fields: list[str] | None = None,
    strict_ai: bool = False,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> tuple[dict[str, str], str]:
    fields = draft_lesson_fields(
        subject=subject,
        grade=grade,
        title=title,
        material=material,
        class_hour=class_hour,
        class_type=class_type,
        teaching_style=teaching_style,
        student_level=student_level,
        generation_depth=generation_depth,
        dynamic_fields=dynamic_fields,
        strict_ai=strict_ai,
        creative_mode=creative_mode,
        anti_repetition_context=anti_repetition_context,
        few_shot_examples=few_shot_examples,
    )
    load_local_env()
    return fields, os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro").strip() or "deepseek-v4-pro"


def draft_lesson_document_fields_with_source(
    subject: str,
    grade: str,
    title: str,
    material: str,
    class_hour: str = "1课时",
    class_type: str = DEFAULT_CLASS_TYPE,
    teaching_style: str = DEFAULT_TEACHING_STYLE,
    student_level: str = DEFAULT_STUDENT_LEVEL,
    generation_depth: str = DEFAULT_GENERATION_DEPTH,
    template_fields: list[str] | None = None,
    strict_ai: bool = False,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> tuple[dict[str, str], str]:
    return draft_lesson_fields_with_source(
        subject=subject,
        grade=grade,
        title=title,
        material=material,
        class_hour=class_hour,
        class_type=class_type,
        teaching_style=teaching_style,
        student_level=student_level,
        generation_depth=generation_depth,
        dynamic_fields=template_fields or JSON_FIELD_NAMES,
        strict_ai=strict_ai,
        creative_mode=creative_mode,
        anti_repetition_context=anti_repetition_context,
        few_shot_examples=few_shot_examples,
    )


def write_lesson_json(fields: dict[str, str], output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fields, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def refine_lesson_field(field: str, value: str, action: str = "more_vivid", instruction: str = "") -> str:
    label = REFINE_ACTIONS.get(action, action or "优化")
    text = (value or "").strip() or "请先生成或填写该字段内容。"
    custom = (instruction or "").strip()

    if is_deepseek_configured():
        prompt = f"""请对一个教案字段做局部优化，只返回 JSON。
字段名：{field}
优化动作：{label}
特别要求：{custom or "无"}

原内容：
{text}

输出要求：
1. 只输出一个 JSON 对象。
2. JSON key 必须是 "value"。
3. 不要输出 Markdown，不要解释。
4. 不要出现模板占位符。"""
        try:
            data = chat_json(
                prompt,
                system="你是教师教案局部润色引擎，只输出合法 JSON。",
                temperature=0.76,
                max_tokens=2500,
            )
            refined = _clean_text(data.get("value"))
            if refined:
                return refined
        except Exception:
            pass

    if action == "shorten":
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines[:4]) or text[:500]

    if action == "clean_blackboard":
        return f"{text}\n\n板书优化：保留主线、关键词和层级关系，减少长句，方便课堂即时呈现。"

    if action == "simplify":
        return (
            f"{text}\n\n"
            "基础班优化：将关键任务拆成“教师示范、同伴互助、独立完成”三步，并补充即时反馈。"
        )

    if action == "deepen_inquiry":
        return (
            f"{text}\n\n"
            "探究深化：增加一个需要学生提出假设、寻找证据并进行迁移应用的问题。"
        )

    if action == "more_interaction":
        return (
            f"{text}\n\n"
            "互动增强：加入同伴互评、小组展示或出口卡，让学生用证据说明自己的理解。"
        )

    extra = f"特别要求：{custom}" if custom else "加入更具体的课堂情境、教师话术和学生可观察活动。"
    return f"{text}\n\n{label}优化：{extra}"
