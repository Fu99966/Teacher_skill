from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LessonPattern:
    key: str
    label: str
    process_frame: str
    method_frame: str
    homework_frame: str
    reflection_frame: str

    def to_dict(self) -> dict:
        return asdict(self)


LESSON_PATTERNS: dict[str, LessonPattern] = {
    "project_lesson": LessonPattern(
        key="project_lesson",
        label="项目课",
        process_frame="项目总任务、课时分配、阶段任务、项目产出、评价方式、总结提升",
        method_frame="项目教学法、任务驱动法、演示教学法、分组协作、巡回指导、作品展示评价",
        homework_frame="阶段成果、项目文档、作品完善、展示汇报",
        reflection_frame="关注任务推进、过程成果、工程规范、小组协作和迭代改进",
    ),
    "training_lesson": LessonPattern(
        key="training_lesson",
        label="实训课",
        process_frame="任务说明、教师示范、学生操作、巡回指导、成果检查、总结反馈",
        method_frame="任务驱动、示范教学、操作训练、巡回指导、即时反馈",
        homework_frame="完成实训记录、整理操作步骤、提交结果截图或实训报告",
        reflection_frame="关注操作规范、常见错误、设备准备和个别学生支持",
    ),
    "experiment_lesson": LessonPattern(
        key="experiment_lesson",
        label="实验课",
        process_frame="实验问题、变量与安全、实验操作、数据记录、现象解释、评价总结",
        method_frame="探究式教学、实验演示、小组合作、数据分析、交流评价",
        homework_frame="整理实验数据、完成实验报告、分析误差来源",
        reflection_frame="关注安全规范、变量控制、数据真实性和结论表达",
    ),
    "review_lesson": LessonPattern(
        key="review_lesson",
        label="复习课",
        process_frame="知识网络、典型问题、错因分析、变式训练、迁移应用、总结提升",
        method_frame="问题驱动、错题讲评、思维导图、分层训练、同伴互助",
        homework_frame="基础巩固、错题订正、变式提升、综合应用",
        reflection_frame="关注知识结构是否形成、薄弱点是否暴露、分层任务是否有效",
    ),
    "regular_lesson": LessonPattern(
        key="regular_lesson",
        label="常规课",
        process_frame="情境导入、新知讲授、课堂互动、巩固练习、课堂总结",
        method_frame="启发式教学、案例教学、讲练结合、小组讨论、课堂反馈",
        homework_frame="基础题、提升题、拓展题",
        reflection_frame="关注目标达成、重难点突破、课堂参与和作业反馈",
    ),
}


def infer_lesson_pattern(class_type: str, teaching_style: str = "", title: str = "", class_hour: str = "") -> LessonPattern:
    text = f"{class_type} {teaching_style} {title} {class_hour}".lower()
    if any(marker in text for marker in ("项目", "pbl", "project")):
        return LESSON_PATTERNS["project_lesson"]
    if any(marker in text for marker in ("实训", "训练", "操作")):
        return LESSON_PATTERNS["training_lesson"]
    if any(marker in text for marker in ("实验", "探究")):
        return LESSON_PATTERNS["experiment_lesson"]
    if any(marker in text for marker in ("复习", "讲评", "习题")):
        return LESSON_PATTERNS["review_lesson"]
    return LESSON_PATTERNS["regular_lesson"]


def pattern_prompt_notes(pattern: LessonPattern) -> str:
    return (
        f"课型模板：{pattern.label}\n"
        f"教学过程建议结构：{pattern.process_frame}\n"
        f"教学方法建议：{pattern.method_frame}\n"
        f"作业建议：{pattern.homework_frame}\n"
        f"反思建议：{pattern.reflection_frame}"
    )
