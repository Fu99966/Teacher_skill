from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


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


def build_lesson_prompt(subject: str, grade: str, title: str, material: str, class_hour: str = "1课时") -> str:
    stage = _stage_name(infer_school_stage(grade))
    fields_json = json.dumps(JSON_FIELD_NAMES, ensure_ascii=False)
    return f"""# 角色设定
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
教材内容/知识点：{material}
"""


def draft_lesson_fields(subject: str, grade: str, title: str, material: str, class_hour: str = "1课时") -> LessonFields:
    """Create a deterministic, stage-aware draft before a real LLM is connected."""
    stage = infer_school_stage(grade)
    focus = _material_focus(material)

    if stage == "primary":
        return _primary_lesson(subject, grade, title, class_hour, focus)
    if stage == "higher":
        return _higher_lesson(subject, grade, title, class_hour, focus)
    return _secondary_lesson(subject, grade, title, class_hour, focus)


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
