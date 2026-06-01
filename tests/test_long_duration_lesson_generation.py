from __future__ import annotations

from teacher_agent.lesson_generator import (
    _local_fallback_fields,
    infer_lesson_scope,
    parse_class_hour_count,
)


def test_parse_class_hour_count_supports_digits_and_chinese_numerals():
    assert parse_class_hour_count("32课时") == 32
    assert parse_class_hour_count("共16课时") == 16
    assert parse_class_hour_count("三课时") == 3
    assert parse_class_hour_count("十六课时") == 16
    assert parse_class_hour_count("1课时") == 1
    assert parse_class_hour_count("32") == 32
    assert parse_class_hour_count("无法识别") == 1


def test_infer_lesson_scope_by_duration_and_training_type():
    assert infer_lesson_scope("1课时") == "single_lesson"
    assert infer_lesson_scope("4课时") == "unit_lesson"
    assert infer_lesson_scope("32课时", "实训课") == "project_lesson"
    assert infer_lesson_scope("8课时", "实训课") == "project_lesson"
    assert infer_lesson_scope("8课时") == "unit_lesson"


def test_pcb_32_hour_local_fallback_generates_project_plan():
    fields = _local_fallback_fields(
        subject="物联网",
        grade="24物联网1班",
        title="PCB板设计",
        material="",
        class_hour="32课时",
        class_type="实训课",
        dynamic_fields=[
            "lesson_title",
            "class_hour",
            "teaching_goals",
            "teaching_key_difficult",
            "teaching_process",
            "teaching_method",
            "homework",
            "reflection",
        ],
    )

    assert "32课时" in fields["class_hour"]

    process = fields["teaching_process"]
    assert "项目" in process
    assert "课时" in process
    assert "课时分配" in process
    assert "阶段" in process
    assert "原理图" in process
    assert "PCB布局" in process or "布局布线" in process
    assert "DRC" in process
    assert "Gerber" in process

    goals = fields["teaching_goals"]
    assert "PCB设计流程" in goals
    assert "DRC检查" in goals
    assert "工程规范意识" in goals

    method = fields["teaching_method"]
    assert "项目教学法" in method
    assert "任务驱动" in method
    assert "巡回指导" in method
    assert "Gerber输出" in method

    assert "阶段作业" in fields["homework"]
    assert "DRC检查记录" in fields["homework"]
    assert "完整流程" in fields["reflection"]
    assert "工程规范意识" in fields["reflection"]
