from __future__ import annotations

from teacher_agent.teacher_agents import merge_revision_preserving_original


def test_revision_empty_values_do_not_override_original():
    original = {
        "lesson_title": "桂林山水",
        "teaching_goals": "理解课文内容",
        "teaching_process": "导入\n探究\n总结",
    }
    revised = {
        "lesson_title": "",
        "teaching_goals": "",
        "teaching_process": "优化后的教学过程",
        "extra": "模板外字段",
    }

    merged = merge_revision_preserving_original(
        original,
        revised,
        ["lesson_title", "teaching_goals", "teaching_process"],
    )

    assert merged == {
        "lesson_title": "桂林山水",
        "teaching_goals": "理解课文内容",
        "teaching_process": "优化后的教学过程",
    }


def test_empty_revision_object_keeps_original():
    original = {"lesson_title": "桂林山水", "teaching_process": "导入"}

    merged = merge_revision_preserving_original(original, {}, ["lesson_title", "teaching_process"])

    assert merged == original
