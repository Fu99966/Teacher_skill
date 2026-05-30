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
    "teaching_key_difficult",
    "teaching_preparation",
    "teaching_environment",
    "teaching_aids",
    "teaching_method",
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
        field = re.sub(r"[\r\n\t<>]", "", field).strip()
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


def validate_non_empty_fields(fields: dict[str, Any], required_fields: list[str]) -> tuple[bool, list[str]]:
    empty_fields = [field for field in _normalize_dynamic_fields(required_fields) if not _clean_text(fields.get(field))]
    return not empty_fields, empty_fields


def backfill_empty_fields_with_local_fallback(
    fields: dict[str, Any],
    *,
    subject: str,
    grade: str,
    title: str,
    material: str,
    class_hour: str,
    required_fields: list[str],
) -> dict[str, str]:
    normalized_fields = _normalize_dynamic_fields(required_fields)
    result = coerce_dynamic_fields(fields if isinstance(fields, dict) else {}, normalized_fields)

    # teaching_method: try deriving from teaching_process FIRST (before generic fallback)
    if not _clean_text(result.get("teaching_method")) and _clean_text(result.get("teaching_process")):
        derived = _derive_teaching_method_from_process(
            result.get("teaching_method", ""), title, result["teaching_process"]
        )
        if derived.strip():
            result["teaching_method"] = derived

    # Then fill remaining empty fields with local fallback
    fallback = _local_fallback_fields(
        subject=subject,
        grade=grade,
        title=title,
        material=material,
        class_hour=class_hour,
        dynamic_fields=normalized_fields,
    )
    for field in normalized_fields:
        if not _clean_text(result.get(field)):
            result[field] = fallback.get(field, "")

    return result


def _derive_teaching_method_from_process(_existing: str, title: str, teaching_process: str) -> str:
    """Generate teaching_method from teaching_process content."""
    tp = teaching_process
    methods: list[str] = []

    # Detect method patterns from teaching_process text
    patterns = [
        ("导入", "情境导入法"),
        ("探究", "探究式学习"),
        ("讨论", "小组讨论法"),
        ("小组", "小组合作学习"),
        ("实验", "实验探究法"),
        ("演示", "演示教学法"),
        ("案例", "案例分析法"),
        ("任务驱动", "任务驱动法"),
        ("练习", "练习法"),
        ("观察", "观察法"),
        ("归纳", "归纳总结法"),
        ("对比", "对比分析法"),
        ("角色扮演", "角色扮演法"),
        ("模拟", "模拟教学法"),
        ("头脑风暴", "头脑风暴法"),
        ("翻转", "翻转课堂"),
        ("微课", "微课辅助教学"),
        ("项目", "项目教学法"),
    ]
    for keyword, method_name in patterns:
        if keyword in tp and method_name not in methods:
            methods.append(method_name)

    if not methods:
        methods = ["讲授法", "问答法", "讨论法"]

    method_text = "、".join(methods)
    return f"本课采用{method_text}相结合的教学方式。教学过程中注重学生主体地位，通过创设情境、组织活动、引导探究和即时反馈，帮助学生理解《{title}》的核心内容。教师在课堂中扮演组织者、引导者和促进者的角色，关注学生的个体差异和课堂生成。"


def _field_label_hint(field_name: str) -> str:
    known = {
        "lesson_title": "课题名称",
        "subject": "学科",
        "grade": "年级",
        "class_hour": "课时",
        "teaching_goals": "教学目标",
        "key_points": "教学重点",
        "difficult_points": "教学难点",
        "teaching_key_difficult": "教学重难点",
        "teaching_preparation": "教学准备",
        "teaching_environment": "教学环境要求",
        "teaching_aids": "教具挂图",
        "teaching_method": "教学方法的运用",
        "student_analysis": "学情分析",
        "teaching_process": "教学过程",
        "teacher_activity": "教师活动",
        "student_activity": "学生活动",
        "design_intent": "设计意图",
        "blackboard_design": "板书设计",
        "homework": "作业设计",
        "reflection": "教学反思",
        "warm_up": "导入或热身环节",
        "safety_rules": "安全注意事项",
        "safety_precautions": "安全注意事项",
        "core_training": "核心训练",
        "assessment": "评价方式",
    }
    return known.get(field_name, field_name.replace("_", " ").replace("-", " "))


def _local_fallback_fields(
    *,
    subject: str,
    grade: str,
    title: str,
    material: str,
    class_hour: str,
    dynamic_fields: list[str],
) -> dict[str, str]:
    material_hint = re.sub(r"\s+", " ", material).strip()
    if len(material_hint) > 140:
        material_hint = material_hint[:140] + "..."

    base: dict[str, str] = {
        "lesson_title": title,
        "subject": subject,
        "grade": grade,
        "teaching_date": "2026年5月29日",
        "class_name": grade,
        "class_type": "新授课",
        "class_hour": class_hour,
        "teaching_goals": f"1. 知识目标：理解《{title}》的核心内容与关键方法。\n2. 能力目标：能结合材料完成分析、表达和迁移应用。\n3. 素养目标：在学习过程中提升合作探究与反思能力。",
        "key_points": f"围绕《{title}》掌握本课核心知识、关键方法和课堂产出要求。",
        "difficult_points": "将抽象知识转化为可观察、可操作、可表达的学习任务，并帮助不同层次学生完成理解迁移。",
        "teaching_key_difficult": f"重点：理解《{title}》的核心知识与方法。\n难点：把知识迁移到新的情境任务中。",
        "teaching_preparation": "多媒体课件、学习任务单、板书材料；学生课前阅读教材并标注疑问。",
        "teaching_environment": f"标准多媒体教室，配备投影设备、白板或智慧黑板，网络畅通。如本课《{title}》涉及实验或实训环节，应具备相应的操作台和演示器材。",
        "teaching_aids": f"PPT课件、教材、学习任务单。如《{title}》涉及实物展示或实验，准备对应的教具和演示材料。",
        "teaching_method": f"采用案例教学、任务驱动、小组讨论和实物演示相结合的方式。通过生活案例导入《{title}》相关概念，组织学生观察分析，再以小组讨论完成应用场景分析。",
        "student_analysis": f"{grade}学生已有一定基础，但对《{title}》中的关键概念和迁移应用仍需要教师提供支架。",
        "teaching_process": f"一、导入新课：创设与《{title}》相关的问题情境，唤起学生已有经验。\n二、新知探究：围绕教学内容组织阅读、观察、讨论和归纳。\n三、巩固应用：完成基础练习与变式任务，教师即时反馈。\n四、课堂总结：学生梳理本课收获和仍需追问的问题。",
        "teacher_activity": "创设情境、提出问题、组织探究、示范方法、反馈评价并总结提升。",
        "student_activity": "观察材料、独立思考、小组交流、完成任务单并进行展示或互评。",
        "design_intent": "通过问题驱动和分层任务，让学生经历理解、应用、表达和反思的完整学习过程。",
        "blackboard_design": f"{title}\n一、核心问题\n二、关键方法\n三、课堂任务\n四、总结提升",
        "homework": f"基础题：整理《{title}》关键知识。\n提升题：完成一道迁移应用任务。\n拓展题：结合生活或教材补充材料提出一个探究问题。",
        "reflection": f"课后重点观察学生对《{title}》核心方法的掌握情况，是否能在新情境中表达和应用；根据反馈调整后续教学节奏和分层练习。",
        "warm_up": f"以《{title}》相关图片、问题或生活情境导入，快速唤起学生已有经验。",
        "safety_rules": "活动前明确材料使用和课堂秩序要求；实验或操作环节需按教师指令进行。",
        "safety_precautions": "提醒学生按规范操作，注意器材、用电、走动和小组协作安全。",
        "core_training": f"围绕《{title}》设置基础识记、方法应用和迁移表达三个层级训练。",
        "assessment": "采用课堂观察、任务单完成情况、小组展示和出口卡进行过程性评价。",
    }
    if material_hint:
        base["teaching_process"] += f"\n教材依据：{material_hint}"

    return {field: base.get(field, f"围绕《{title}》生成“{_field_label_hint(field)}”相关内容。") for field in dynamic_fields}


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
    template_context: dict[str, Any] | None = None,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> str:
    fields = _normalize_dynamic_fields(dynamic_fields)
    fields_json = json.dumps(fields, ensure_ascii=False)
    stage = _stage_name(infer_school_stage(grade))
    material_text = material.strip() or "用户没有提供教材内容，请生成通用版教案，并避免编造具体教材页码。"
    creative = creative_mode.strip() or "常规稳健"

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

    context_block = ""
    if template_context:
        context_block = f"""
# 模板字段上下文
以下信息来自 Word 模板解析，用于理解字段语义和填充位置。请结合 label、row_text、source 推断未知字段含义：
{json.dumps(template_context, ensure_ascii=False, indent=2)}
"""

    return f"""
# 角色设定
你是由小学高级教师、中学特级教师、大学资深教授组成的“全学段特级教师团队”。你熟悉教育心理学、认知发展规律、课程标准和课堂落地写法。

# 核心任务
根据用户提供的课程信息，为 Word 模板自动填充生成教学文档内容。
你必须输出一个纯 JSON 对象，JSON 的 Key 必须严格且仅包含以下字段：
{fields_json}

请根据字段字面意思生成对应内容。字段可能来自学校 Word 模板，不一定是标准教案字段；例如 warm_up、safety_rules、core_training、assessment 等，都要按字段语义生成可直接填入模板的文本。

# 学段差异化原则
当前识别学段：{stage}
1. 小学阶段：激发兴趣、习惯养成、直观感知，多用情境导入、实物展示、小组互助。
2. 中学阶段：知识体系构建、逻辑思维培养、考点对齐，强调自主探究、典型例题、变式训练和迁移应用。
3. 大学阶段：学术视野、专业前沿、独立研究与实践应用，采用研讨式、案例教学或项目驱动。

# 动态生成要求
1. 课型适配：本次课型为【{class_type}】，内容必须符合该课型典型特征。
2. 教学法/风格：采用【{teaching_style}】组织课堂。
3. 学情自适应：目标学生群体为【{student_level}】，在难点突破、教师话术、课堂活动和作业设计中体现针对性。
4. 生成深度：输出深度为【{generation_depth}】。
5. 风格控制：本次生成风格为【{creative}】。
6. 模板优先：不要新增模板字段之外的 Key；不要遗漏给定字段；不要输出模板占位符。
{anti_repetition_block}
{few_shot_block}
{context_block}

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


def _draft_lesson_fields_ai(
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
    template_context: dict[str, Any] | None = None,
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
        template_context=template_context,
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
    template_context: dict[str, Any] | None = None,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> dict[str, str]:
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
        dynamic_fields=dynamic_fields,
        strict_ai=strict_ai,
        template_context=template_context,
        creative_mode=creative_mode,
        anti_repetition_context=anti_repetition_context,
        few_shot_examples=few_shot_examples,
    )[0]


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
    template_context: dict[str, Any] | None = None,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> tuple[dict[str, str], str]:
    fields = _normalize_dynamic_fields(dynamic_fields)
    try:
        data = _draft_lesson_fields_ai(
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
            strict_ai=strict_ai,
            template_context=template_context,
            creative_mode=creative_mode,
            anti_repetition_context=anti_repetition_context,
            few_shot_examples=few_shot_examples,
        )
        ok, empty_fields = validate_non_empty_fields(data, fields)
        if not ok and strict_ai:
            retry_context = (anti_repetition_context + "\n\n请特别注意：上一轮生成存在空字段，请务必为所有模板字段生成非空内容。").strip()
            data = _draft_lesson_fields_ai(
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
                strict_ai=strict_ai,
                template_context=template_context,
                creative_mode=creative_mode,
                anti_repetition_context=retry_context,
                few_shot_examples=few_shot_examples,
            )
            ok, empty_fields = validate_non_empty_fields(data, fields)
            if not ok:
                raise LessonGenerationError(f"AI 生成结果存在空字段，已重试仍未补齐：{', '.join(empty_fields)}")
        if not ok:
            data = backfill_empty_fields_with_local_fallback(
                data,
                subject=subject,
                grade=grade,
                title=title,
                material=material,
                class_hour=class_hour,
                required_fields=fields,
            )
            return data, "deepseek_with_local_backfill"
        load_local_env()
        return data, os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro").strip() or "deepseek-v4-pro"
    except Exception:
        if strict_ai:
            raise
        return (
            _local_fallback_fields(
                subject=subject,
                grade=grade,
                title=title,
                material=material,
                class_hour=class_hour,
                dynamic_fields=fields,
            ),
            "local_fallback",
        )


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
    template_context: dict[str, Any] | None = None,
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
        template_context=template_context,
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
4. 不要出现模板占位符。
"""
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
        return f"{text}\n\n基础班优化：将关键任务拆成“教师示范、同伴互助、独立完成”三步，并补充即时反馈。"

    if action == "deepen_inquiry":
        return f"{text}\n\n探究深化：增加一个需要学生提出假设、寻找证据并进行迁移应用的问题。"

    if action == "more_interaction":
        return f"{text}\n\n互动增强：加入同伴互评、小组展示或出口卡，让学生用证据说明自己的理解。"

    extra = f"特别要求：{custom}" if custom else "加入更具体的课堂情境、教师话术和学生可观察活动。"
    return f"{text}\n\n{label}优化：{extra}"
