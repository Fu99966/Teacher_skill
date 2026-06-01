from __future__ import annotations

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"


def _read_web_file(relative_path: str) -> str:
    return (WEB_ROOT / relative_path).read_text(encoding="utf-8")


def test_homepage_is_single_prompt_mode():
    html = _read_web_file("index.html")

    assert "一句话生成教案" in html
    assert "一句话需求" in html
    assert "使用学校 Word 模板" in html
    assert "教材内容 / 补充资料" in html
    assert "生成教案" in html
    assert "按模板填写教案" not in html
    assert "新手模式" not in html
    assert "专业模式" not in html
    assert "智能体框架" not in html
    assert "工作流图" not in html
    assert "Agent trace" not in html
    assert "高级诊断" in html
    assert "教案质量判断" in html


def test_step_bar_has_teacher_friendly_steps():
    html = _read_web_file("index.html")

    assert "输入需求" in html
    assert "生成内容" in html
    assert "预览编辑" in html
    assert "导出 Word" in html


def test_field_labels_and_preview_groups_use_real_template_fields():
    js = _read_web_file("static/app.js")

    assert 'teaching_method: "教学方法的运用"' in js
    assert 'teaching_key_difficult: "重点难点"' in js
    assert 'teaching_environment: "对教学环境的要求"' in js
    assert 'teaching_aids: "教具挂图"' in js
    assert 'teaching_process: "主要教学内容"' in js
    assert 'teaching_goals: "教学目的"' in js
    assert 'reflection: "课后小记"' in js
    assert '{ title: "教学过程与方法", keys: ["teaching_process", "teaching_method"] }' in js


def test_teaching_method_guard_and_local_derive_hook_are_wired():
    js = _read_web_file("static/app.js")

    assert "function deriveTeachingMethod" in js
    assert "derive_from_process" in js
    assert "function updateTeachingMethodGuard" in js
    assert "教学方法的运用为空，请补充后再导出。" in js
    assert "teaching_method" in js


def test_example_prompt_buttons_are_wired():
    html = _read_web_file("index.html")
    js = _read_web_file("static/app.js")

    assert "实训课示例" in html
    assert "公开课示例" in html
    assert "常规课示例" in html
    assert "PCB板设计" in js
    assert "传感器基础" in js
    assert "物联网通信基础" in js
    assert "examplePrompts" in js
    assert "requestSubmit" not in js.split("document.querySelectorAll(\"[data-example]\")", 1)[-1].split("lessonForm.addEventListener", 1)[0]


def test_css_contains_card_layout_step_bar_and_toast():
    css = _read_web_file("static/app.css")

    assert "max-width" in css
    assert ".main-card" in css
    assert ".step-bar" in css
    assert ".preview-card" in css
    assert ".delivery-card" in css
    assert ".toast" in css
    assert "width: min(780px" in css


def _input_tag(html: str, name: str) -> str:
    match = re.search(rf"<input\b[^>]*\bname=\"{name}\"[^>]*>", html)
    assert match, f"missing input name={name}"
    return match.group(0)


def test_first_screen_has_no_native_required_course_or_template_fields():
    html = _read_web_file("index.html")

    assert 'id="supplement-fields" hidden' in html
    for name in ("subject", "grade", "title"):
        assert "required" not in _input_tag(html, name)
    assert "required" not in _input_tag(html, "template")
    assert "\u4e25\u683c AI \u6a21\u5f0f" not in html


def test_single_prompt_js_defaults_to_fallback_and_system_template():
    js = _read_web_file("static/app.js")

    assert 'formData.set("strict_ai", "0")' in js
    assert 'runData.set("template_mode", useSchoolTemplate.checked ? "upload" : "system")' in js
    assert "if (useSchoolTemplate.checked && !templateInput.files.length)" in js
    assert "\u8bf7\u4e0a\u4f20\u5b66\u6821 Word \u6a21\u677f" in js


def test_long_duration_scope_hint_is_wired():
    html = _read_web_file("index.html")
    js = _read_web_file("static/app.js")

    assert 'id="scope-hint"' in html
    assert "function parseClassHourCount" in js
    assert "function updateLessonScopeHint" in js
    assert "\u5df2\u8bc6\u522b\u4e3a\u957f\u8bfe\u65f6\u9879\u76ee/\u5355\u5143\u6559\u6848" in js
    assert "\u5f53\u524d\u5185\u5bb9\u53ef\u80fd\u4ecd\u504f\u5355\u8bfe\u65f6" in js
