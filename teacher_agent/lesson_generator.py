from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


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


def build_lesson_prompt(subject: str, grade: str, title: str, material: str, class_hour: str = "1课时") -> str:
    return f"""你是有经验的一线教师，请根据以下信息生成教案字段 JSON。

要求：
1. 只输出 JSON，不输出 Markdown。
2. 字段必须包含 lesson_title, subject, grade, class_hour, teaching_goals, key_points, difficult_points, teaching_preparation, teaching_process, blackboard_design, homework, reflection。
3. 内容适合对应年级，语言清晰，可直接填入 Word 教案模板。
4. 不要生成 Word 格式，不要加入占位符。

学科：{subject}
年级：{grade}
课题：{title}
课时：{class_hour}
教材内容：
{material}
"""


def draft_lesson_fields(subject: str, grade: str, title: str, material: str, class_hour: str = "1课时") -> LessonFields:
    """Create a deterministic draft.

    This placeholder generator lets the project run before an LLM provider is connected.
    Replace this function with a real model call when deploying.
    """
    short_material = material.strip().replace("\r\n", "\n")
    if len(short_material) > 180:
        short_material = short_material[:180] + "..."

    return LessonFields(
        lesson_title=title,
        subject=subject,
        grade=grade,
        class_hour=class_hour,
        teaching_goals=(
            f"1. 理解《{title}》的核心内容，能用自己的话概括主要信息。\n"
            "2. 掌握本课关键知识点，并能在课堂练习中迁移运用。\n"
            "3. 在讨论、朗读或探究活动中提升表达能力和合作意识。"
        ),
        key_points=f"围绕“{title}”梳理核心知识，理解教材中的重点内容和学习方法。",
        difficult_points="引导学生把文本、知识点或问题情境与自身经验联系起来，形成较深入的理解。",
        teaching_preparation="教师准备教材、课件、板书设计和课堂练习；学生课前预习相关内容。",
        teaching_process=(
            "一、情境导入：结合生活经验或图片材料引出课题，激发学习兴趣。\n"
            f"二、整体感知：学生阅读或观察材料，初步了解《{title}》的主要内容。\n"
            "三、重点探究：围绕关键问题开展讲解、讨论和练习，突破教学重点。\n"
            "四、合作交流：组织小组分享学习发现，教师适时点拨提升。\n"
            "五、课堂小结：师生共同归纳本课收获，形成清晰的知识结构。\n"
            "六、巩固练习：完成分层练习，及时反馈学习效果。"
        ),
        blackboard_design=f"{title}\n教学重点：理解核心内容\n学习方法：阅读、讨论、归纳\n课堂收获：知识掌握与能力提升",
        homework="1. 整理本课知识要点。\n2. 完成配套练习。\n3. 结合课堂内容写一段学习收获。",
        reflection=f"本课可继续根据学生课堂反馈调整活动难度。教材摘要：{short_material}",
    )


def write_lesson_json(fields: LessonFields, output_path: str | Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fields.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path
