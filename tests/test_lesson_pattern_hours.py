from __future__ import annotations

from teacher_agent.lesson_patterns import infer_lesson_pattern
from teacher_agent.rag_context import build_knowledge_context


def test_long_class_hour_infers_project_lesson_without_project_keyword():
    pattern = infer_lesson_pattern(
        class_type="常规课",
        teaching_style="启发式",
        title="STM32智能小车课程",
        class_hour="32课时",
    )

    assert pattern.key == "project_lesson"
    assert "项目总任务" in pattern.process_frame


def test_rag_context_uses_class_hour_for_lesson_pattern():
    context = build_knowledge_context(
        "课程标准：学生需要完成阶段任务、调试记录和作品展示。",
        subject="物联网",
        title="STM32智能小车课程",
        class_type="常规课",
        teaching_style="启发式",
        class_hour="32课时",
    )

    assert context.lesson_pattern["key"] == "project_lesson"
