from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from .deepseek_client import DeepSeekError, chat_json, is_deepseek_configured


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
    "more_vivid": "更生动",
    "deepen_inquiry": "深化探究",
    "simplify": "降低难度",
    "more_interaction": "增加互动",
    "shorten": "精简表达",
}


@dataclass
class LessonFields:
    lesson_title: str
    subject: str
    grade: str
    class_hour: str
    teaching_goals: str
    key_points: str
    difficult_points: str
    teaching_preparation: str
    teaching_process: str
    blackboard_design: str
    homework: str
    reflection: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def infer_school_stage(grade: str) -> str:
    text = grade.strip()
    higher_markers = ["大学", "本科", "专科", "高职", "研究生", "硕士", "博士", "大一", "大二", "大三", "大四"]
    secondary_markers = ["初中", "高中", "中学", "初一", "初二", "初三", "高一", "高二", "高三", "七年级", "八年级", "九年级"]
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


def _material_focus(material: str) -> str:
    text = re.sub(r"\s+", " ", material).strip()
    if not text:
        return "教材核心知识点"
    return text[:120] + ("..." if len(text) > 120 else "")


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
    template_fields: list[str] | None = None,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> str:
    stage = _stage_name(infer_school_stage(grade))
    fields = template_fields or JSON_FIELD_NAMES
    fields_json = json.dumps(fields, ensure_ascii=False)
    creative_mode = (creative_mode or "常规稳妥").strip()
    anti_repetition_block = ""
    if anti_repetition_context.strip():
        anti_repetition_block = f"""
# 历史反重复要求
以下是系统检索到的近期相似教案摘要。你必须避免复用其中的导入方式、活动顺序、作业表达和板书结构；如果课题相同，也要换一种课堂主线。
{anti_repetition_context}
"""
    few_shot_block = ""
    if few_shot_examples.strip():
        few_shot_block = f"""
# 优秀教案参考样例
以下样例只用于学习质量、颗粒度和课堂活动设计方式，不能照抄措辞。
{few_shot_examples}
"""
    blueprint_block = f"""# 教学设计蓝图要求
在输出 JSON 前，请先在内部完成一份“教学设计蓝图”，但不要把蓝图作为额外字段输出。蓝图必须明确：
1. 本课课堂主线是什么，不能只是“导入-新授-练习-总结”。
2. 学生会完成什么可观察产出。
3. 教师如何用追问、证据、评价推动学习。
4. 本次生成风格为【{creative_mode}】，请在教学过程、作业和板书中体现差异。
5. 至少设计一个与课题强相关的具体课堂活动，不要写泛泛的“小组讨论”。
{anti_repetition_block}
{few_shot_block}
"""
    return f"""{blueprint_block}
# 角色设定
你是一个由多位顶尖教育专家组成的“全学段特级教师团队”化身。你的团队成员包括小学高级教师、中学特级教师以及大学资深教授。你深谙各个学段的教育心理学、认知发展规律和各学科的课程标准。

# 核心任务
你的任务是根据用户提供的【学科】、【年级】、【课题】、【课时】和【教材内容/知识点】，生成一份结构严谨、专业度高且可直接落地的教案。
你需要将生成的教案内容严格转化为标准的 JSON 数据格式，以便系统能够自动将其填充到 Word 模板中。

# 学段差异化教学原则
当前识别学段：{stage}

1. 小学阶段（1-6年级）：
   - 核心：激发兴趣、习惯养成、直观感知。
   - 设计：多使用游戏化教学、情境导入、实物展示、小组互助。语言要生动活泼，难点需拆解为简单步骤。
2. 中学阶段（初中、高中）：
   - 核心：知识体系构建、逻辑思维培养、中高考考点对齐。
   - 设计：强调自主探究、批判性思维、知识迁移与应用。教学过程需严谨，包含新课讲授、典型例题剖析、变式训练。
3. 大学阶段（本科、专科）：
   - 核心：学术视野、专业前沿、独立研究与实践应用。
   - 设计：采用研讨式、案例教学或项目驱动。弱化机械记忆，强调文献阅读、课堂辩论、实验设计及行业前沿结合。

# 字段内容规范
- lesson_title：课题名称，需简洁准确。
- subject：学科。
- grade：年级。
- class_hour：课时安排。
- teaching_goals：教学目标，必须分条列出，可用知识与技能、过程与方法、情感态度与价值观，或新课标核心素养维度。
- key_points：教学重点，明确本节课必须掌握的核心知识。
- difficult_points：教学难点，指出学生最容易混淆或难以理解的知识点。
- teaching_preparation：教学准备，如教具、多媒体课件、实验器材、学生预习任务等。
- teaching_process：教学过程，必须包含详细环节。每个环节需简述教师活动和学生活动。
- blackboard_design：板书设计，结构化、精炼，能直观反映课堂脉络。
- homework：作业或课后任务，需体现分层：基础题、提升题、拓展/探究题。
- reflection：教学反思预设，基于该课题常见问题提供课后反思方向。

# 创造力与多样性指令
每次生成教案时，必须根据课型、教学法和学情调整教学过程，避免千篇一律的“导入-新授-练习-总结”。
如果用户选择 BOPPPS、5E、PBL、游戏化、翻转课堂等模型，请将模型结构融入 teaching_process，但不要空喊模型名称，要体现具体师生互动。

# 动态生成要求
1. 课型适配：本次课型为【{class_type}】，教学过程必须符合该课型的典型特征。
2. 教学法/风格：采用【{teaching_style}】组织课堂。
3. 学情自适应：目标学生群体为【{student_level}】，在难点突破、教师话术、课堂活动和作业分层中体现针对性。
4. 生成深度：输出深度为【{generation_depth}】。如果是精简，表达更短；如果是深度，增加探究、评价和迁移。
5. 模板字段：如果 JSON Key 来自模板占位符，请严格围绕字段名语义生成内容，不要新增模板之外的 Key。

# 严格输出限制
1. 绝对不要输出任何 Markdown 格式，也不要输出任何解释性前言或后语。
2. 唯一输出必须是一个合法的、可以直接被 JSON.parse() 解析的纯 JSON 字符串。
3. 请勿在生成的文本中加入 {{{{ 或 }}}} 这样的模板占位符。
4. JSON 的 Key 必须严格使用以下英文字段名：{fields_json}

# 用户输入
学科：{subject}
年级：{grade}
课题：{title}
课时：{class_hour}
课型：{class_type}
教学法/风格：{teaching_style}
学生层次：{student_level}
生成深度：{generation_depth}
教材内容/知识点：{material}
"""


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
) -> LessonFields:
    return draft_lesson_fields_with_source(
        subject,
        grade,
        title,
        material,
        class_hour,
        class_type,
        teaching_style,
        student_level,
        generation_depth,
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
    strict_ai: bool = False,
    creative_mode: str = "",
    anti_repetition_context: str = "",
    few_shot_examples: str = "",
) -> tuple[LessonFields, str]:
    """Create a stage-aware draft.

    When DEEPSEEK_API_KEY is configured, DeepSeek is used for real generation.
    The deterministic local generator remains as a safe fallback.
    """
    fallback = draft_lesson_fields_local(
        subject,
        grade,
        title,
        material,
        class_hour,
        class_type,
        teaching_style,
        student_level,
        generation_depth,
    )
    if not is_deepseek_configured():
        if strict_ai:
            raise DeepSeekError(
                "DEEPSEEK_API_KEY is not configured",
                error_type="not_configured",
                user_message="严格 AI 模式已开启，但未配置 DEEPSEEK_API_KEY。请先创建 .env。",
            )
        return fallback, "local"

    prompt = build_lesson_prompt(
        subject,
        grade,
        title,
        material,
        class_hour,
        class_type,
        teaching_style,
        student_level,
        generation_depth,
        JSON_FIELD_NAMES,
        creative_mode,
        anti_repetition_context,
        few_shot_examples,
    )
    try:
        data = chat_json(
            prompt,
            system="你是教师文档 JSON 生成引擎。只输出合法 JSON，不输出 Markdown，不输出解释。",
            temperature=0.82,
            max_tokens=7000,
        )
        return _lesson_fields_from_dict(data, fallback), "deepseek"
    except DeepSeekError:
        if strict_ai:
            raise
        return fallback, "local_fallback"
    except Exception as exc:
        if strict_ai:
            raise DeepSeekError(
                str(exc),
                error_type="unknown",
                user_message=f"DeepSeek 生成失败：{exc}",
            ) from exc
        return fallback, "local_fallback"


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
    """Create a document field map guided by Word template placeholders."""
    fields = template_fields or JSON_FIELD_NAMES
    local_lesson = draft_lesson_fields_local(
        subject,
        grade,
        title,
        material,
        class_hour,
        class_type,
        teaching_style,
        student_level,
        generation_depth,
    )
    fallback = _document_fields_from_lesson(local_lesson, fields)
    if not is_deepseek_configured():
        if strict_ai:
            raise DeepSeekError(
                "DEEPSEEK_API_KEY is not configured",
                error_type="not_configured",
                user_message="严格 AI 模式已开启，但未配置 DEEPSEEK_API_KEY。请先创建 .env。",
            )
        return fallback, "local"

    prompt = build_lesson_prompt(
        subject,
        grade,
        title,
        material,
        class_hour,
        class_type,
        teaching_style,
        student_level,
        generation_depth,
        fields,
        creative_mode,
        anti_repetition_context,
        few_shot_examples,
    )
    try:
        data = chat_json(
            prompt,
            system="你是教育文档 JSON 生成引擎。只输出合法 JSON，不输出 Markdown，不输出解释。",
            temperature=0.82,
            max_tokens=7600,
        )
        return _document_fields_from_dict(data, fallback, fields), "deepseek"
    except DeepSeekError:
        if strict_ai:
            raise
        return fallback, "local_fallback"
    except Exception as exc:
        if strict_ai:
            raise DeepSeekError(
                str(exc),
                error_type="unknown",
                user_message=f"DeepSeek 生成失败：{exc}",
            ) from exc
        return fallback, "local_fallback"


def _document_fields_from_lesson(lesson: LessonFields, template_fields: list[str]) -> dict[str, str]:
    base = lesson.to_dict()
    result = dict(base)
    for field in template_fields:
        if field not in result:
            result[field] = _dynamic_template_field_default(field, base)
    return result


def _document_fields_from_dict(data: dict, fallback: dict[str, str], template_fields: list[str]) -> dict[str, str]:
    allowed = set(JSON_FIELD_NAMES) | set(template_fields)
    result = dict(fallback)
    for key, value in data.items():
        if key not in allowed or value is None:
            continue
        if isinstance(value, (list, tuple)):
            text = "\n".join(str(item) for item in value)
        elif isinstance(value, dict):
            text = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            text = str(value)
        text = text.replace("{{", "").replace("}}", "").strip()
        if text:
            result[key] = text
    for field in template_fields:
        if field not in result:
            result[field] = _dynamic_template_field_default(field, result)
    return result


def _dynamic_template_field_default(field: str, base: dict[str, str]) -> str:
    key = field.lower()
    title = base.get("lesson_title", "本课")
    subject = base.get("subject", "学科")
    grade = base.get("grade", "学生")
    if "safety" in key or "安全" in field:
        return (
            f"1. 活动前明确《{title}》相关课堂规则，提醒学生按要求使用学习材料或实验器材。\n"
            "2. 小组合作时保持有序交流，避免追逐、抢拿器材或离开指定区域。\n"
            "3. 教师巡视重点关注操作安全、情绪状态和突发情况，必要时及时暂停活动。"
        )
    if "warm" in key or "热身" in field:
        return (
            f"围绕《{title}》设置 3-5 分钟热身任务：教师抛出生活化问题或展示材料，"
            f"引导{grade}学生快速唤醒已有经验，并用一句话说出自己的初步发现。"
        )
    if "training" in key or "practice" in key or "训练" in field:
        return (
            f"核心训练围绕{subject}关键能力展开：先完成基础识记或观察任务，再进行变式应用，"
            "最后用开放问题检验学生能否迁移到新情境。"
        )
    if "assessment" in key or "evaluation" in key or "评价" in field:
        return (
            "采用过程性评价与结果性评价结合：观察小组讨论质量、课堂表达证据、练习完成情况，"
            "并用出口卡收集学生仍需追问的问题。"
        )
    if "resource" in key or "material" in key or "资源" in field or "材料" in field:
        return "教材文本、多媒体课件、学习任务单、分层练习单，以及与课堂情境相关的图片或案例材料。"
    if "unit" in key or "单元" in field:
        return f"本课作为单元学习的一环，承接前置知识，并为后续围绕《{title}》的迁移应用与综合表达做准备。"
    return f"围绕《{title}》生成“{field}”内容，需符合{grade}{subject}课堂实际，教师可结合学校模板进一步微调。"


def draft_lesson_fields_local(
    subject: str,
    grade: str,
    title: str,
    material: str,
    class_hour: str = "1课时",
    class_type: str = DEFAULT_CLASS_TYPE,
    teaching_style: str = DEFAULT_TEACHING_STYLE,
    student_level: str = DEFAULT_STUDENT_LEVEL,
    generation_depth: str = DEFAULT_GENERATION_DEPTH,
) -> LessonFields:
    """Create a deterministic, stage-aware draft without an external LLM."""
    stage = infer_school_stage(grade)
    focus = _material_focus(material)

    if stage == "primary":
        lesson = _primary_lesson(subject, grade, title, class_hour, focus)
    elif stage == "higher":
        lesson = _higher_lesson(subject, grade, title, class_hour, focus)
    else:
        lesson = _secondary_lesson(subject, grade, title, class_hour, focus)

    return _apply_diversity_controls(lesson, stage, focus, class_type, teaching_style, student_level, generation_depth)


def _lesson_fields_from_dict(data: dict, fallback: LessonFields) -> LessonFields:
    merged = fallback.to_dict()
    for key in JSON_FIELD_NAMES:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            merged[key] = "\n".join(str(item) for item in value)
        elif isinstance(value, dict):
            merged[key] = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            text = str(value).replace("{{", "").replace("}}", "").strip()
            if text:
                merged[key] = text
    return LessonFields(**merged)


def coerce_lesson_fields(data: dict, fallback: LessonFields) -> LessonFields:
    """Convert model JSON into complete lesson fields with a fallback."""
    return _lesson_fields_from_dict(data, fallback)


def _normalize_option(value: str, fallback: str) -> str:
    value = (value or "").strip()
    return value or fallback


def _student_adjustment(student_level: str) -> str:
    level = _normalize_option(student_level, DEFAULT_STUDENT_LEVEL)
    if "培优" in level or "学优" in level or "挑战" in level:
        return "针对学有余力学生，增加开放性追问、跨学科联系和高阶表达任务，鼓励形成独立观点。"
    if "补弱" in level or "基础" in level or "薄弱" in level:
        return "针对基础薄弱学生，增加示范、步骤支架、同伴互助和即时反馈，确保核心知识当堂过关。"
    return "针对常规混合班，采用分层提问和小组互助，让不同基础学生都能获得适切挑战。"


def _depth_note(generation_depth: str) -> str:
    depth = _normalize_option(generation_depth, DEFAULT_GENERATION_DEPTH)
    if "精简" in depth:
        return "流程保持紧凑，突出关键活动和可执行步骤。"
    if "深度" in depth or "专家" in depth:
        return "流程增加探究证据、评价任务和迁移应用，便于形成高质量课堂记录。"
    return "流程保持完整，兼顾可执行性和课堂生成空间。"


def _process_by_style(title: str, focus: str, class_type: str, teaching_style: str, student_level: str, generation_depth: str) -> str:
    class_type = _normalize_option(class_type, DEFAULT_CLASS_TYPE)
    style = _normalize_option(teaching_style, DEFAULT_TEACHING_STYLE)
    student_note = _student_adjustment(student_level)
    depth_note = _depth_note(generation_depth)

    if "BOPPPS" in style or "参与式" in style:
        return (
            "一、Bridge 导入连接\n"
            f"教师活动：用与“{title}”相关的真实问题或课堂小测连接旧知，快速激活经验。\n"
            "学生活动：用30秒写下已有认识和最想解决的问题。\n\n"
            "二、Objective 明确目标\n"
            "教师活动：把本课目标转化为可观察任务，说明完成标准。\n"
            "学生活动：根据目标勾选自己已有基础，形成个人学习期待。\n\n"
            "三、Pre-assessment 前测诊断\n"
            f"教师活动：围绕“{focus}”设计2-3个诊断题，判断学生起点。\n"
            "学生活动：独立作答并说明理由，暴露易错点。\n\n"
            "四、Participatory Learning 参与式建构\n"
            "教师活动：组织同伴互教、小组证据整理和代表展示，追问思路来源。\n"
            "学生活动：在讨论、操作或文本证据中形成结论，并修正原有理解。\n\n"
            "五、Post-assessment 后测反馈\n"
            "教师活动：用变式任务检测目标达成，现场反馈共性问题。\n"
            "学生活动：完成出口卡，写出一个收获和一个仍需追问的问题。\n\n"
            f"六、Summary 总结迁移\n教师活动：回扣目标并布置分层迁移任务。{student_note}{depth_note}"
        )

    if "5E" in style or "探究" in style or "实验" in class_type:
        return (
            "一、Engage 吸引与设疑\n"
            f"教师活动：呈现与“{title}”相关的现象、材料或矛盾问题，引发认知冲突。\n"
            "学生活动：提出猜想，记录想验证的问题。\n\n"
            "二、Explore 探究与取证\n"
            f"教师活动：围绕“{focus}”提供探究材料、观察路径或实验任务，强调证据意识。\n"
            "学生活动：小组分工观察、操作、圈画或记录数据，形成初步发现。\n\n"
            "三、Explain 解释与建构\n"
            "教师活动：引导学生用学科语言解释发现，补充关键概念和方法。\n"
            "学生活动：用证据支持观点，修正不完整表述。\n\n"
            "四、Elaborate 迁移与应用\n"
            "教师活动：设置新情境任务，引导学生把方法迁移到相似或更复杂问题。\n"
            "学生活动：独立尝试后同伴互评，说明迁移依据。\n\n"
            f"五、Evaluate 评价与反思\n教师活动：用表现性任务评价学习成果。学生活动：完成自评与互评。{student_note}{depth_note}"
        )

    if "项目" in style or "PBL" in style or "活动" in class_type or "拓展" in class_type:
        return (
            "一、发布项目任务\n"
            f"教师活动：把“{title}”转化为一个真实成果任务，明确作品标准和合作规则。\n"
            "学生活动：理解任务要求，选择角色并制定小组计划。\n\n"
            "二、问题拆解与资料建构\n"
            f"教师活动：围绕“{focus}”引导学生拆分关键问题，提供必要支架。\n"
            "学生活动：检索材料、整理证据，形成小组观点或方案。\n\n"
            "三、方案制作与中途反馈\n"
            "教师活动：巡视指导，针对逻辑、表达、证据和合作问题进行点拨。\n"
            "学生活动：完善作品，记录被追问后的修改依据。\n\n"
            "四、成果展示与同伴评价\n"
            "教师活动：组织展示、追问和评价，强调观点质量与学习过程。\n"
            "学生活动：展示成果，回应质询，吸收同伴建议。\n\n"
            f"五、复盘迁移\n教师活动：总结项目中的核心知识、方法和价值。{student_note}{depth_note}"
        )

    if "复习" in class_type:
        return (
            "一、目标回收与知识唤醒\n"
            f"教师活动：围绕“{title}”展示知识清单和易错清单，明确复习目标。\n"
            "学生活动：自查掌握情况，标出薄弱点。\n\n"
            "二、知识网络重构\n"
            f"教师活动：引导学生把“{focus}”纳入知识结构图，建立概念联系。\n"
            "学生活动：补全思维导图，说明节点之间的关系。\n\n"
            "三、典型错误诊断\n"
            "教师活动：呈现代表性错例，追问错因和修正路径。\n"
            "学生活动：判断错误类型，完成同类题修正。\n\n"
            "四、变式迁移训练\n"
            "教师活动：设置基础巩固、综合迁移和挑战拓展任务。\n"
            "学生活动：分层完成练习并交流策略。\n\n"
            f"五、复盘与个人计划\n教师活动：指导学生形成后续复习计划。{student_note}{depth_note}"
        )

    if "讲评" in class_type or "习题" in class_type:
        return (
            "一、数据反馈与问题聚焦\n"
            f"教师活动：展示与“{title}”相关的作业或测评数据，锁定高频错点。\n"
            "学生活动：对照自己的答案定位错误原因。\n\n"
            "二、错因分类与例题剖析\n"
            f"教师活动：围绕“{focus}”归纳概念误解、审题偏差、表达不规范等错因。\n"
            "学生活动：用错因标签标注自己的问题。\n\n"
            "三、同伴讲评与教师追问\n"
            "教师活动：安排学生讲解典型题，追问关键步骤和依据。\n"
            "学生活动：补充、质疑并修正解题过程。\n\n"
            "四、变式补偿训练\n"
            "教师活动：设计同源变式题，检测是否真正迁移。\n"
            "学生活动：独立完成并写出防错提醒。\n\n"
            f"五、错题沉淀\n教师活动：指导学生形成错题卡和二次练习计划。{student_note}{depth_note}"
        )

    if "游戏" in style:
        return (
            "一、任务闯关导入\n"
            f"教师活动：把“{title}”设计成闯关任务，设置情境角色和积分规则。\n"
            "学生活动：领取任务卡，带着问题进入学习。\n\n"
            "二、合作解锁新知\n"
            f"教师活动：围绕“{focus}”设置线索卡、提示卡和挑战卡。\n"
            "学生活动：小组合作寻找证据、完成操作或表达挑战。\n\n"
            "三、擂台展示与即时反馈\n"
            "教师活动：组织小组展示，针对关键知识进行点拨和纠偏。\n"
            "学生活动：展示答案并评价其他小组策略。\n\n"
            "四、升级练习与迁移挑战\n"
            "教师活动：提供基础关、提升关、挑战关任务。\n"
            "学生活动：自主选择任务层级，完成后领取反馈。\n\n"
            f"五、荣誉总结\n教师活动：用关键词归纳本课方法，强调学习习惯。{student_note}{depth_note}"
        )

    return (
        "一、问题导入\n"
        f"教师活动：提出与“{title}”相关的真实问题，明确学习目标和评价标准。\n"
        "学生活动：联系已有经验，提出初步判断。\n\n"
        "二、核心学习任务\n"
        f"教师活动：围绕“{focus}”设计问题链，引导学生经历观察、分析、表达和修正。\n"
        "学生活动：独立思考后小组交流，形成有依据的表达。\n\n"
        "三、互动建构与重点突破\n"
        "教师活动：针对关键难点提供支架、示范和追问。\n"
        "学生活动：用例证、数据或文本证据解释观点。\n\n"
        "四、迁移应用\n"
        "教师活动：设置分层任务，检测学生能否迁移到新情境。\n"
        "学生活动：完成练习，说明思路并互评。\n\n"
        f"五、总结反思\n教师活动：回扣目标，形成板书结构。学生活动：完成学习反思。{student_note}{depth_note}"
    )


def _apply_diversity_controls(
    lesson: LessonFields,
    stage: str,
    focus: str,
    class_type: str,
    teaching_style: str,
    student_level: str,
    generation_depth: str,
) -> LessonFields:
    class_type = _normalize_option(class_type, DEFAULT_CLASS_TYPE)
    teaching_style = _normalize_option(teaching_style, DEFAULT_TEACHING_STYLE)
    student_level = _normalize_option(student_level, DEFAULT_STUDENT_LEVEL)
    generation_depth = _normalize_option(generation_depth, DEFAULT_GENERATION_DEPTH)

    process = _process_by_style(
        lesson.lesson_title,
        focus,
        class_type,
        teaching_style,
        student_level,
        generation_depth,
    )
    student_note = _student_adjustment(student_level)
    depth_note = _depth_note(generation_depth)

    preparation_extra = "教学模型任务卡、分层学习单、课堂评价记录表。"
    if "实验" in class_type or "探究" in teaching_style:
        preparation_extra = "探究任务单、观察记录表、必要实验器材或可视化材料。"
    elif "项目" in teaching_style or "PBL" in teaching_style:
        preparation_extra = "项目任务书、成果评价量规、资料包和小组分工表。"
    elif "讲评" in class_type:
        preparation_extra = "错因统计表、典型错例、变式训练单和错题整理卡。"

    goals = lesson.teaching_goals + f"\n4. 课堂策略目标：围绕“{class_type}”和“{teaching_style}”，提升学生参与度、表达质量和迁移能力。"
    difficulty = lesson.difficult_points + f"\n针对学情：{student_note}"
    preparation = lesson.teaching_preparation + f" {preparation_extra}"
    homework = lesson.homework + f"\n个性化任务：{student_note}"
    reflection = lesson.reflection + f"\n多样化反思：本课采用“{class_type} + {teaching_style}”，课后需观察该组合是否真正提升学生参与、理解和迁移。{depth_note}"

    if stage == "higher":
        homework += "\n研究延伸：补充一篇文献、案例或行业资料，形成课堂后续讨论问题。"

    return replace(
        lesson,
        teaching_goals=goals,
        difficult_points=difficulty,
        teaching_preparation=preparation,
        teaching_process=process,
        homework=homework,
        reflection=reflection,
    )


def refine_lesson_field(field: str, value: str, action: str = "more_vivid", instruction: str = "") -> str:
    label = REFINE_ACTIONS.get(action, action or "优化")
    text = (value or "").strip()
    custom = (instruction or "").strip()
    if not text:
        text = "请先生成或填写该字段内容。"

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
                system="你是教师教案局部润色引擎。只输出合法 JSON。",
                temperature=0.76,
                max_tokens=2500,
            )
            refined = str(data.get("value") or "").replace("{{", "").replace("}}", "").strip()
            if refined:
                return refined
        except Exception:
            pass

    if action == "shorten":
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        shortened = "\n".join(lines[:4])
        return f"{shortened}\n优化说明：已压缩为更适合直接放入模板的精简版本。"

    if action == "simplify":
        return (
            f"{text}\n\n"
            "补弱优化：\n"
            "1. 将关键任务拆成“先观察、再模仿、后独立完成”三个步骤。\n"
            "2. 每个环节提供一句示范话术或一个例子，降低理解门槛。\n"
            "3. 增加即时反馈，确保基础学生能当堂完成核心目标。"
        )

    if action == "deepen_inquiry":
        return (
            f"{text}\n\n"
            "探究深化：\n"
            "1. 增加一个需要学生提出假设或解释原因的追问。\n"
            "2. 要求学生用证据支持观点，避免只给结论。\n"
            "3. 设计迁移任务，把本课方法应用到新材料或新情境。"
        )

    if action == "more_interaction":
        return (
            f"{text}\n\n"
            "互动增强：\n"
            "1. 增加同伴互评或小组展示，要求学生说明理由。\n"
            "2. 设置教师追问：你从哪里看出来？还有不同想法吗？\n"
            "3. 用出口卡收集学生仍然困惑的问题，作为下一步教学依据。"
        )

    vivid_prefix = "生动化优化" if action == "more_vivid" else f"{label}优化"
    custom_line = f"\n特别要求：{custom}" if custom else ""
    return (
        f"{text}\n\n"
        f"{vivid_prefix}：\n"
        f"1. 增加贴近学生经验的情境，让任务更有画面感。{custom_line}\n"
        "2. 教师话术更具体，避免空泛指令。\n"
        "3. 学生活动以可观察行为呈现，方便教师直接落地。"
    )


def _primary_lesson(subject: str, grade: str, title: str, class_hour: str, focus: str) -> LessonFields:
    return LessonFields(
        lesson_title=title,
        subject=subject,
        grade=grade,
        class_hour=class_hour,
        teaching_goals=(
            "1. 知识与技能：能说出本课的主要内容，理解与课题相关的核心知识点。\n"
            "2. 过程与方法：通过观察、朗读、操作、交流等活动，学会用简单步骤解决学习任务。\n"
            "3. 情感态度与习惯：在情境体验和小组互助中保持学习兴趣，养成认真倾听、主动表达和及时整理的习惯。"
        ),
        key_points=f"围绕“{title}”建立直观认识，掌握本课最基本、最关键的知识或方法。",
        difficult_points="把抽象或容易混淆的内容拆解成可观察、可操作、可表达的简单步骤，帮助学生真正理解。",
        teaching_preparation="多媒体课件、图片或实物材料、学习单、小组活动卡；学生课前尝试阅读或观察与课题有关的生活现象。",
        teaching_process=(
            "一、情境导入\n"
            f"教师活动：用图片、故事、实物或小游戏引出“{title}”，提出贴近生活的问题。\n"
            "学生活动：观察材料，说一说自己的发现或已有经验。\n\n"
            "二、新知探究\n"
            f"教师活动：围绕教材内容“{focus}”分步讲解，借助板书、图示或动作演示降低理解难度。\n"
            "学生活动：边看边想，完成学习单中的圈画、连线、口头表达或简单操作。\n\n"
            "三、课堂互动与巩固\n"
            "教师活动：组织同桌互说、小组合作或闯关练习，及时纠正常见错误。\n"
            "学生活动：在游戏化任务中练习核心知识，互相补充答案。\n\n"
            "四、课堂总结\n"
            "教师活动：带领学生用关键词回顾“学了什么、怎样学、还想知道什么”。\n"
            "学生活动：用一句话说出本课收获，并整理学习单。"
        ),
        blackboard_design=f"{title}\n一、看一看：发现问题\n二、想一想：理解重点\n三、说一说：表达方法\n四、练一练：巩固运用",
        homework=(
            "基础题：完成教材或学习单中的基础练习，巩固本课关键词和基本方法。\n"
            "提升题：用自己的话向家人讲一讲本课最重要的内容。\n"
            "拓展题：在生活中找一个与本课有关的例子，画一画或写一写。"
        ),
        reflection=f"课后重点观察学生是否真正理解“{title}”的核心内容，尤其关注参与度较低或表达困难的学生。若学生对步骤掌握不牢，应在下一课增加实物演示、同伴互助和分层练习。",
    )


def _secondary_lesson(subject: str, grade: str, title: str, class_hour: str, focus: str) -> LessonFields:
    return LessonFields(
        lesson_title=title,
        subject=subject,
        grade=grade,
        class_hour=class_hour,
        teaching_goals=(
            "1. 知识与技能：准确理解本课核心概念、规律或方法，能完成典型题和基础迁移任务。\n"
            "2. 过程与方法：通过问题链、自主探究、例题剖析和变式训练，形成分析问题与解决问题的基本思路。\n"
            "3. 核心素养/情感态度：在比较、归纳和表达中提升逻辑思维、证据意识和学科表达能力。"
        ),
        key_points=f"围绕“{title}”构建清晰知识框架，掌握核心概念、关键方法及其典型应用。",
        difficult_points="学生容易停留在记忆层面，难以区分相近概念、理解推理过程或把知识迁移到新情境中。",
        teaching_preparation="多媒体课件、典型例题与变式训练单、课堂检测题；学生课前预习教材相关内容并标出疑问。",
        teaching_process=(
            "一、导入新课\n"
            f"教师活动：呈现与“{title}”相关的问题情境或考点情境，明确本课学习任务。\n"
            "学生活动：独立思考并提出初步判断，暴露已有认知和疑问。\n\n"
            "二、新知探究\n"
            f"教师活动：围绕教材内容“{focus}”设计问题链，引导学生经历概念形成、规律归纳或方法建构。\n"
            "学生活动：阅读材料、记录证据、小组讨论，尝试用学科语言解释核心问题。\n\n"
            "三、典型例题剖析\n"
            "教师活动：选择具有代表性的例题，示范审题、建模、推理或规范表达，指出易错点。\n"
            "学生活动：跟随分析过程，归纳解题步骤和判断依据。\n\n"
            "四、变式训练与迁移应用\n"
            "教师活动：设置基础、变式、综合三个层级任务，及时反馈学生错误。\n"
            "学生活动：独立完成练习，说明思路，并对同伴答案进行修正。\n\n"
            "五、课堂总结\n"
            "教师活动：用结构图梳理知识脉络，回扣本课重点和考试/评价要求。\n"
            "学生活动：完成课堂小结，写出一个仍需巩固的问题。"
        ),
        blackboard_design=f"{title}\n1. 核心概念/问题\n2. 关键方法：审题-分析-推理-表达\n3. 易错点：概念混淆、步骤遗漏、迁移不足\n4. 应用：典型题-变式题-综合题",
        homework=(
            "基础题：完成教材或练习册中对应基础题，巩固概念和基本方法。\n"
            "提升题：完成2-3道变式题，写清关键步骤和理由。\n"
            "拓展/探究题：联系真实情境或跨章节知识，完成一道综合应用题或小研究任务。"
        ),
        reflection=f"课后需重点分析学生在“{title}”中的易错点：是概念理解不清、方法步骤不熟，还是迁移应用不足。下一课可根据课堂检测结果补充变式训练和错因讲评。",
    )


def _higher_lesson(subject: str, grade: str, title: str, class_hour: str, focus: str) -> LessonFields:
    return LessonFields(
        lesson_title=title,
        subject=subject,
        grade=grade,
        class_hour=class_hour,
        teaching_goals=(
            "1. 知识与理论：理解本专题的核心概念、理论框架及其在学科体系中的位置。\n"
            "2. 研究与方法：能够基于案例、文献或数据提出问题，进行分析、论证和反思。\n"
            "3. 实践与创新：将所学内容迁移到真实项目、实验设计或行业问题中，形成独立观点。"
        ),
        key_points=f"把握“{title}”的理论框架、关键问题、典型案例及其专业应用价值。",
        difficult_points="学生可能缺少跨文献整合、批判性分析和真实情境建模能力，需要通过案例、研讨和项目任务深化理解。",
        teaching_preparation="课程讲义、核心文献或案例材料、数据/实验/项目任务说明；学生课前完成指定阅读并提交问题清单。",
        teaching_process=(
            "一、问题导入与学术定位\n"
            f"教师活动：介绍“{title}”的学科背景、现实价值和前沿问题，明确本次课的研讨目标。\n"
            "学生活动：基于课前阅读提出问题，说明自己对主题的初步理解。\n\n"
            "二、理论框架与案例分析\n"
            f"教师活动：围绕“{focus}”讲解核心理论，提供典型案例或研究材料，引导学生识别变量、证据和论证路径。\n"
            "学生活动：分组分析案例，提炼观点并与理论框架建立联系。\n\n"
            "三、研讨式互动或项目任务\n"
            "教师活动：组织专题辩论、问题研讨、实验设计或项目方案评审，追问假设、证据和局限。\n"
            "学生活动：展示小组分析结果，对同伴观点进行质询、补充和修正。\n\n"
            "四、实践迁移与前沿拓展\n"
            "教师活动：联系行业应用、研究前沿或真实项目，提示后续学习路径。\n"
            "学生活动：提出一个可继续研究或实践的问题，并说明可能的方法。\n\n"
            "五、课堂总结\n"
            "教师活动：总结本专题的知识结构、方法价值和开放问题。\n"
            "学生活动：完成学习札记，记录一个理论收获和一个研究疑问。"
        ),
        blackboard_design=f"{title}\n理论框架：核心概念-关键机制-应用场景\n研究路径：问题-证据-论证-反思\n实践迁移：案例分析/项目设计/前沿拓展",
        homework=(
            "基础任务：整理本课核心概念和理论框架，形成一页学习笔记。\n"
            "提升任务：阅读1篇相关文献或案例，提炼研究问题、方法和结论。\n"
            "拓展/探究任务：设计一个小型研究、实验或项目方案，说明问题、路径和预期成果。"
        ),
        reflection=f"课后需反思学生是否能围绕“{title}”进行证据化表达和批判性讨论。若课堂研讨停留在观点陈述层面，后续应加强文献阅读指导、案例拆解和研究方法训练。",
    )


def write_lesson_json(fields: LessonFields, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fields.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
