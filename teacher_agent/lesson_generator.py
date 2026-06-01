from __future__ import annotations

import json
import os
import re
from difflib import SequenceMatcher
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


FIELD_LABEL_TITLES = {
    "教学方法的运用",
    "主要教学内容",
    "教学目的",
    "重点难点",
    "作业",
    "课后小记",
    "教学方法",
    "教学过程",
    "教学目标",
    "教学重难点",
    "作业设计",
    "教学反思",
}

PCB_PROJECT_PREPARATION = "计算机机房、EDA设计软件、PCB示例板、原理图素材、元件封装库、DRC规则说明、项目任务单、评价表。"
PCB_PROJECT_MATERIAL_BASIS = "依据物联网应用技术专业课程要求、PCB设计项目任务书、EDA软件操作规范和实训教学目标组织教学。"
GENERAL_MATERIAL_BASIS = "依据课程标准、教材内容、课堂教学目标和学生学情组织教学。"


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def normalize_topic_key(text: str) -> str:
    """Normalize topic names for keyword routing, e.g. PCB 板设计 -> PCB板设计."""
    compact = re.sub(r"[\s\u3000]+", "", str(text or ""))
    compact = re.sub(r"[《》“”\"'，,。.:：;；、\-_/\\|()（）\[\]【】{}]+", "", compact)
    return compact.upper()


def _extract_title_from_request(agent_request: str) -> str:
    match = re.search(r"《([^》]{1,80})》", str(agent_request or ""))
    return match.group(1).strip() if match else ""


def sanitize_lesson_title(title: str, agent_request: str, fallback_title: str = "") -> str:
    """Prevent template field labels such as 教学方法的运用 from becoming the lesson title."""
    request_title = _extract_title_from_request(agent_request)
    if request_title:
        return request_title

    cleaned = str(title or "").strip()
    if cleaned and _compact_text(cleaned) not in {_compact_text(label) for label in FIELD_LABEL_TITLES}:
        return cleaned

    fallback = str(fallback_title or "").strip()
    if fallback and _compact_text(fallback) not in {_compact_text(label) for label in FIELD_LABEL_TITLES}:
        return fallback

    return "未命名课题"


def is_generation_request_text(text: str) -> bool:
    """Return True when text is a teacher's generation instruction, not course material."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return False
    compact = _compact_text(cleaned)
    has_generation_verb = any(marker in compact for marker in ("帮我生成", "生成一份", "写一份", "做一份", "请生成", "帮我写"))
    has_lesson_doc = "教案" in compact or "教学设计" in compact or "备课" in compact
    if has_generation_verb and has_lesson_doc:
        return True
    if "课时" in compact and has_lesson_doc and any(marker in compact for marker in ("生成", "帮我", "写", "做")):
        return True
    if len(compact) <= 80 and "生成" in compact and has_lesson_doc:
        return True
    prompt_like_markers = (
        "适合",
        "实训课",
        "项目式教学",
        "24级",
        "24物联网",
        "PCB板设计",
        "PCB设计",
    )
    compact_upper = compact.upper()
    marker_hits = sum(1 for marker in prompt_like_markers if marker.upper() in compact_upper)
    return has_lesson_doc and "课时" in compact and marker_hits >= 1


def sanitize_material_hint(material: str, agent_request: str = "", title: str = "") -> str:
    """Keep natural-language generation prompts out of 教材依据."""
    cleaned = re.sub(r"\s+", " ", str(material or "")).strip()
    if not cleaned:
        return ""

    compact_material = _compact_text(cleaned)
    compact_request = _compact_text(agent_request)
    if compact_request and compact_material:
        ratio = SequenceMatcher(None, compact_material, compact_request).ratio()
        if compact_material == compact_request or ratio >= 0.72:
            return ""

    if is_generation_request_text(cleaned):
        return ""

    if "《" in cleaned and "》" in cleaned and "课时" in cleaned and "教案" in cleaned:
        return ""
    compact = _compact_text(cleaned)
    compact_title = _compact_text(title)
    if "课时" in compact and "教案" in compact and (not compact_title or compact_title in compact):
        return ""

    return cleaned


def is_pcb_project_lesson(title: str, class_hour: str = "", class_type: str = "") -> bool:
    return "PCB" in normalize_topic_key(title) and infer_lesson_scope(class_hour, class_type) == "project_lesson"


def default_material_basis(title: str, class_hour: str = "", class_type: str = "") -> str:
    if is_pcb_project_lesson(title, class_hour, class_type):
        return PCB_PROJECT_MATERIAL_BASIS
    return GENERAL_MATERIAL_BASIS


def normalize_lesson_field_aliases(fields: dict[str, Any], agent_request: str = "") -> dict[str, Any]:
    """Normalize final fields before preview/export so aliases cannot drift apart."""
    result = dict(fields or {})
    title = str(result.get("lesson_title") or result.get("title") or "")
    class_hour = str(result.get("class_hour") or "")
    class_type = str(result.get("class_type") or "")

    if is_pcb_project_lesson(title, class_hour, class_type):
        result["teaching_preparation"] = PCB_PROJECT_PREPARATION
        result["teaching_aids"] = PCB_PROJECT_PREPARATION
        result["teaching_resources"] = PCB_PROJECT_PREPARATION
        result["preparation"] = PCB_PROJECT_PREPARATION
    else:
        preparation = (
            result.get("teaching_preparation")
            or result.get("teaching_aids")
            or result.get("teaching_resources")
            or result.get("preparation")
            or ""
        )
        if preparation:
            result.setdefault("teaching_preparation", preparation)
            result.setdefault("teaching_aids", preparation)

    process = str(result.get("teaching_process") or "")
    if process:
        basis_pattern = re.compile(r"教材依据[：:]\s*([^\r\n]*)")

        def replace_basis(match: re.Match[str]) -> str:
            current_basis = match.group(1).strip()
            clean_basis = sanitize_material_hint(current_basis, agent_request, title)
            if clean_basis:
                return f"教材依据：{clean_basis}"
            return f"教材依据：{default_material_basis(title, class_hour, class_type)}"

        result["teaching_process"] = basis_pattern.sub(replace_basis, process)
    return result


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


_CHINESE_NUMBER_MAP = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _parse_chinese_integer(text: str) -> int:
    text = text.strip()
    if not text:
        return 0
    if "十" not in text:
        value = 0
        for char in text:
            if char not in _CHINESE_NUMBER_MAP:
                return 0
            value = value * 10 + _CHINESE_NUMBER_MAP[char]
        return value

    left, _, right = text.partition("十")
    tens = _CHINESE_NUMBER_MAP.get(left, 1) if left else 1
    ones = _CHINESE_NUMBER_MAP.get(right, 0) if right else 0
    return tens * 10 + ones


def parse_class_hour_count(class_hour: str) -> int:
    """Parse a class-hour string such as 32课时, 共十六课时, or 三课时."""
    text = str(class_hour or "").strip()
    if not text:
        return 1
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

    digit_match = re.search(r"(\d+)", text)
    if digit_match:
        try:
            return max(1, int(digit_match.group(1)))
        except ValueError:
            return 1

    chinese_match = re.search(r"([零〇一二两三四五六七八九十]+)\s*(?:课时|节|课)?", text)
    if chinese_match:
        parsed = _parse_chinese_integer(chinese_match.group(1))
        if parsed > 0:
            return parsed
    return 1


def infer_lesson_scope(class_hour: str, class_type: str = "") -> str:
    """Infer whether fallback should draft a single lesson, unit lesson, or project lesson."""
    count = parse_class_hour_count(class_hour)
    if "实训" in str(class_type or "") and count >= 8:
        return "project_lesson"
    if count <= 2:
        return "single_lesson"
    if count <= 8:
        return "unit_lesson"
    return "project_lesson"


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
    class_type: str = "",
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
        class_type=class_type,
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
    class_type: str = "",
) -> dict[str, str]:
    scope = infer_lesson_scope(class_hour, class_type)
    hour_count = parse_class_hour_count(class_hour)
    hour_text = class_hour.strip() or f"{hour_count}课时"
    title_text = sanitize_lesson_title(title, material, title)
    material_hint = sanitize_material_hint(material, "", title_text)
    if len(material_hint) > 140:
        material_hint = material_hint[:140] + "..."
    topic_key = normalize_topic_key(title_text)
    is_pcb = "PCB" in topic_key

    single_process = f"一、导入新课：创设与《{title_text}》相关的问题情境，唤起学生已有经验。\n二、新知探究：围绕教学内容组织阅读、观察、讨论和归纳。\n三、巩固应用：完成基础练习与变式任务，教师即时反馈。\n四、课堂总结：学生梳理本课收获和仍需追问的问题。"
    unit_process = f"一、单元导入：明确《{title_text}》的学习主题、核心问题和阶段目标。\n二、核心知识学习：分课时梳理关键概念、方法和典型案例，形成知识网络。\n三、任务训练：围绕核心知识设置分层任务，组织学生完成练习、讨论和展示。\n四、综合应用：设计综合情境任务，引导学生迁移运用并修正理解偏差。\n五、评价总结：通过任务单、展示互评和教师点评完成单元回顾。"
    if is_pcb and scope == "project_lesson":
        project_process = f"本项目共{hour_text}，围绕“完成一块物联网节点控制板PCB设计”展开。\n一、项目总任务：学生以小组为单位完成从需求分析、原理图绘制、封装检查、PCB布局布线、DRC检查到Gerber文件输出的完整设计流程。\n二、课时分配表：\n第一阶段：项目导入与PCB基础认知（4课时），认识PCB设计流程、工程规范和项目评价标准。\n第二阶段：原理图设计与元件封装检查（6课时），完成原理图绘制、网络标号、元件封装匹配与电气规则初查。\n第三阶段：PCB布局与布线规范训练（8课时），完成板框设置、元件布局、关键信号布线、电源与地线处理。\n第四阶段：DRC检查与问题修改（6课时），根据DRC报告定位短路、间距、未连接网络等问题并迭代修改。\n第五阶段：Gerber文件输出与项目文档整理（4课时），完成Gerber、钻孔文件、BOM和项目说明文档整理。\n第六阶段：作品展示、互评与总结提升（4课时），开展小组汇报、作品互评、教师点评和工程经验复盘。\n三、阶段任务：每个阶段形成可检查的过程性成果，教师进行巡回指导和即时反馈。\n四、项目产出：原理图文件、PCB布局布线文件、DRC检查记录、Gerber输出文件、项目说明书和展示汇报。\n五、评价方式：过程表现、阶段成果、工程规范、问题修正质量、小组协作和最终作品展示综合评价。\n六、总结提升：引导学生复盘PCB设计中的规则意识、质量意识和工程迭代方法。"
    else:
        project_process = f"本项目共{hour_text}，围绕《{title_text}》设计项目化整体教学方案。\n一、项目总任务：明确真实任务情境、成果要求和评价标准，学生以小组方式完成完整项目。\n二、课时分配表：项目导入与任务拆解（2课时）；核心知识学习与方法示范（{max(2, hour_count // 4)}课时）；阶段任务训练与巡回指导（{max(3, hour_count // 3)}课时）；综合应用与成果完善（{max(2, hour_count // 4)}课时）；作品展示、评价反馈与总结提升（2课时）。\n三、阶段任务：按“认知准备—方法训练—项目实践—成果完善—展示评价”推进，每阶段都有明确学习产出。\n四、项目产出：学习任务单、阶段成果、项目作品、展示汇报和反思记录。\n五、评价方式：过程评价、成果评价、小组互评和教师评价结合。\n六、总结提升：复盘知识迁移、合作过程和质量改进方法。"

    if scope == "project_lesson" and is_pcb:
        preparation = PCB_PROJECT_PREPARATION
        teaching_aids = PCB_PROJECT_PREPARATION
        goals = "1. 知识目标：理解PCB设计流程、元件封装、布局布线、DRC检查、Gerber输出等核心知识。\n2. 能力目标：能完成从原理图到PCB布局布线、规则检查和文件输出的完整设计任务。\n3. 素养目标：形成工程规范意识、团队协作意识和质量改进意识。"
        teaching_method = "采用项目教学法、任务驱动法、演示教学法、分组协作、巡回指导和作品展示评价相结合的方式。教师围绕原理图绘制、PCB布局布线、DRC检查、Gerber输出和作品展示组织阶段任务，学生在真实项目实践中完成设计、检查、修改和汇报。"
        homework = "阶段作业：\n1. 完成PCB设计流程思维导图；\n2. 完成原理图绘制与封装检查；\n3. 提交PCB布局布线文件；\n4. 完成DRC检查记录；\n5. 整理Gerber输出文件和项目说明书。"
        reflection = "课后重点反思：学生是否掌握PCB设计完整流程；是否能发现并修改DRC问题；小组协作和工程规范意识是否提升；后续是否需要加强封装、布线和设计规则训练。"
        key_points = "PCB设计流程、原理图绘制、封装匹配、布局布线规范、DRC检查和Gerber文件输出。"
        difficult_points = "将工程规范落实到PCB布局布线细节中，并能依据DRC检查结果定位问题、修正设计。"
    elif scope == "project_lesson":
        preparation = "多媒体课件、项目任务单、阶段成果模板、小组协作记录表、展示评价表和必要的实训材料。"
        teaching_aids = "PPT课件、项目任务单、阶段成果样例、评价量规和展示材料。"
        goals = f"1. 知识目标：系统理解《{title_text}》项目任务所需的核心概念、方法流程和评价标准。\n2. 能力目标：能按阶段完成项目任务，形成可展示、可评价的学习成果。\n3. 素养目标：提升任务规划、团队协作、问题解决和持续改进意识。"
        teaching_method = "采用项目教学法、任务驱动法、演示教学法、分组协作、巡回指导和作品展示评价相结合的方式，围绕项目阶段任务推动学生完成学习产出。"
        homework = f"阶段作业：\n1. 完成《{title_text}》项目任务拆解表；\n2. 完成阶段学习任务单；\n3. 提交项目过程成果；\n4. 根据评价反馈修改完善作品；\n5. 整理项目说明和个人反思。"
        reflection = f"课后重点关注学生是否理解《{title_text}》项目完整流程，是否能按阶段完成任务并修正问题，小组协作、表达展示和质量改进意识是否提升。"
        key_points = f"《{title_text}》项目任务流程、阶段产出要求和综合应用方法。"
        difficult_points = "把分散知识整合到项目任务中，并持续根据反馈改进成果质量。"
    elif scope == "unit_lesson":
        preparation = "多媒体课件、学习任务单、单元知识结构图、综合任务材料和展示评价表。"
        teaching_aids = f"PPT课件、教材、单元任务单、知识结构图。如《{title_text}》涉及实物展示或实验，准备对应的教具和演示材料。"
        goals = f"1. 知识目标：系统理解《{title_text}》单元核心概念和知识结构。\n2. 能力目标：能通过任务训练完成知识迁移和综合应用。\n3. 素养目标：提升持续探究、合作表达和反思改进能力。"
        teaching_method = "采用单元整体教学、任务驱动、小组讨论、案例分析和展示评价相结合的方式，帮助学生形成知识结构并完成综合应用。"
        homework = f"基础任务：整理《{title_text}》单元知识结构图。\n提升任务：完成综合应用练习并说明解题思路。\n拓展任务：围绕单元核心问题提出一个新的应用场景。"
        reflection = f"课后关注学生是否形成《{title_text}》的整体知识框架，是否能在综合任务中迁移应用，并据此调整后续分层训练。"
        key_points = f"《{title_text}》单元核心知识、方法链条和综合应用任务。"
        difficult_points = "帮助学生把多课时内容组织成稳定的知识结构，并完成迁移应用。"
    else:
        preparation = "多媒体课件、学习任务单、板书材料；学生课前阅读教材并标注疑问。"
        teaching_aids = f"PPT课件、教材、学习任务单。如《{title_text}》涉及实物展示或实验，准备对应的教具和演示材料。"
        goals = f"1. 知识目标：理解《{title_text}》的核心内容与关键方法。\n2. 能力目标：能结合材料完成分析、表达和迁移应用。\n3. 素养目标：在学习过程中提升合作探究与反思能力。"
        teaching_method = f"采用案例教学、任务驱动、小组讨论和实物演示相结合的方式。通过生活案例导入《{title_text}》相关概念，组织学生观察分析，再以小组讨论完成应用场景分析。"
        homework = f"基础题：整理《{title_text}》关键知识。\n提升题：完成一道迁移应用任务。\n拓展题：结合生活或教材补充材料提出一个探究问题。"
        reflection = f"课后重点观察学生对《{title_text}》核心方法的掌握情况，是否能在新情境中表达和应用；根据反馈调整后续教学节奏和分层练习。"
        key_points = f"围绕《{title_text}》掌握本课核心知识、关键方法和课堂产出要求。"
        difficult_points = "将抽象知识转化为可观察、可操作、可表达的学习任务，并帮助不同层次学生完成理解迁移。"

    teaching_process = {
        "single_lesson": single_process,
        "unit_lesson": unit_process,
        "project_lesson": project_process,
    }[scope]

    base: dict[str, str] = {
        "lesson_title": title_text,
        "subject": subject,
        "grade": grade,
        "teaching_date": "2026年5月29日",
        "class_name": grade,
        "class_type": class_type or ("项目实训课" if scope == "project_lesson" else "新授课"),
        "class_hour": hour_text,
        "teaching_goals": goals,
        "key_points": key_points,
        "difficult_points": difficult_points,
        "teaching_key_difficult": f"重点：{key_points}\n难点：{difficult_points}",
        "teaching_preparation": preparation,
        "teaching_resources": preparation,
        "preparation": preparation,
        "teaching_environment": f"标准多媒体教室，配备投影设备、白板或智慧黑板，网络畅通。如本课《{title_text}》涉及实验或实训环节，应具备相应的操作台和演示器材。",
        "teaching_aids": teaching_aids,
        "teaching_method": teaching_method,
        "student_analysis": f"{grade}学生已有一定基础，但对《{title_text}》中的关键概念和迁移应用仍需要教师提供支架。",
        "teaching_process": teaching_process,
        "teacher_activity": "创设情境、提出问题、组织探究、示范方法、反馈评价并总结提升。",
        "student_activity": "观察材料、独立思考、小组交流、完成任务单并进行展示或互评。",
        "design_intent": "通过问题驱动和分层任务，让学生经历理解、应用、表达和反思的完整学习过程。",
        "blackboard_design": f"{title_text}\n一、核心问题\n二、关键方法\n三、课堂任务\n四、总结提升",
        "homework": homework,
        "reflection": reflection,
        "warm_up": f"以《{title_text}》相关图片、问题或生活情境导入，快速唤起学生已有经验。",
        "safety_rules": "活动前明确材料使用和课堂秩序要求；实验或操作环节需按教师指令进行。",
        "safety_precautions": "提醒学生按规范操作，注意器材、用电、走动和小组协作安全。",
        "core_training": f"围绕《{title_text}》设置基础识记、方法应用和迁移表达三个层级训练。",
        "assessment": "采用课堂观察、任务单完成情况、小组展示和出口卡进行过程性评价。",
    }
    if material_hint:
        base["teaching_process"] += f"\n教材依据：{material_hint}"
    elif scope == "project_lesson" and is_pcb:
        base["teaching_process"] += f"\n教材依据：{PCB_PROJECT_MATERIAL_BASIS}"
    else:
        base["teaching_process"] += f"\n教材依据：{GENERAL_MATERIAL_BASIS}"

    base = normalize_lesson_field_aliases(base)
    return {field: base.get(field, f"围绕《{title_text}》生成“{_field_label_hint(field)}”相关内容。") for field in dynamic_fields}


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
                class_type=class_type,
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
                class_type=class_type,
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
    if field == "teaching_method" and action == "derive_from_process":
        return _derive_teaching_method_from_process("", instruction or "", value or "")

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
