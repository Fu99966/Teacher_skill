from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"


def _read_web_file(relative_path: str) -> str:
    return (WEB_ROOT / relative_path).read_text(encoding="utf-8")


def test_homepage_uses_two_teacher_entries_not_mode_switches():
    html = _read_web_file("index.html")

    assert "新手模式" not in html
    assert "专业模式" not in html
    assert "按模板填写教案" in html
    assert "一句话生成教案" in html
    assert "上传学校 Word 模板" in html
    assert "一句话需求" in html
    assert "智能体框架" not in html
    assert "高级诊断" in html


def test_field_labels_include_real_lesson_template_fields():
    js = _read_web_file("static/app.js")

    assert 'teaching_method: "教学方法的运用"' in js
    assert 'teaching_key_difficult: "重点难点"' in js
    assert 'teaching_environment: "对教学环境的要求"' in js
    assert 'teaching_aids: "教具挂图"' in js
    assert 'teaching_process: "主要教学内容"' in js
    assert 'teaching_goals: "教学目的"' in js
    assert 'reflection: "课后小记"' in js
    assert 'key_points: "教学重点"' not in js
    assert 'difficult_points: "教学难点"' not in js
    assert 'teaching_preparation: "教学准备"' not in js
    assert 'blackboard_design: "板书设计"' not in js


def test_preview_groups_keep_process_and_method_together():
    js = _read_web_file("static/app.js")

    assert '{ title: "教学过程与方法", keys: ["teaching_process", "teaching_method"] }' in js
