from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"


def _read_web_file(relative_path: str) -> str:
    return (WEB_ROOT / relative_path).read_text(encoding="utf-8")


def test_teacher_homepage_keeps_single_task_and_optional_template_upload():
    html = _read_web_file("index.html")

    assert "一句话生成教案" in html
    assert "一句话需求" in html
    assert "使用学校 Word 模板" in html
    assert "上传 .docx 模板" in html
    assert "教材内容 / 补充资料" in html
    assert "生成教案" in html
    assert "按模板填写教案" not in html
    assert "新手模式" not in html
    assert "专业模式" not in html
    assert "智能体框架" not in html


def test_teacher_examples_are_visible_but_not_auto_submit():
    html = _read_web_file("index.html")
    js = _read_web_file("static/app.js")

    assert "实训课示例" in html
    assert "公开课示例" in html
    assert "常规课示例" in html
    assert "帮我生成一份 24物联网1班《PCB板设计》的实训课教案，适合项目式教学，课时 2 课时。" in js
    assert "帮我生成一份《传感器基础》的公开课教案，要求有情境导入、学生互动和评价反馈。" in js
    assert "帮我生成一份《物联网通信基础》的常规课教案，内容简洁，适合日常备课。" in js
    example_handler = js.split('document.querySelectorAll("[data-example]")', 1)[-1].split("lessonForm.addEventListener", 1)[0]
    assert "agentRequest.value" in example_handler
    assert "requestSubmit" not in example_handler


def test_teacher_preview_and_delivery_language_is_non_technical():
    html = _read_web_file("index.html")
    js = _read_web_file("static/app.js")

    assert "预览编辑" in html
    assert "确认字段内容" in html
    assert "教案质量判断" in html
    assert "主要风险" in html
    assert "建议" in html
    assert "交付检查" in html
    assert "下载 Word 教案" in html
    assert "返回编辑" in html
    assert "evaluateQuality" in js
    assert "可提交" in js
    assert "建议修改" in js
    assert "不可提交" in js


def test_teacher_method_guard_still_blocks_export_until_method_exists():
    js = _read_web_file("static/app.js")

    assert 'teaching_method: "教学方法的运用"' in js
    assert 'teaching_process: "主要教学内容"' in js
    assert "function updateTeachingMethodGuard" in js
    assert "exportButton.disabled = blocked" in js
    assert "教学方法的运用为空，请补充后再导出。" in js
    assert "deriveMethodButton" in js
    assert "derive_from_process" in js


def test_teacher_visual_contract_uses_warm_card_style():
    css = _read_web_file("static/app.css")

    assert "--dark: #141413" in css
    assert "--light: #faf9f5" in css
    assert "--border: #e8e6dc" in css
    assert "--accent: #d97757" in css
    assert "--accent-h: #c46849" in css
    assert "--green: #788c5d" in css
    assert "--error: #d85c47" in css
    assert "--radius: 8px" in css
    assert "max-width" in css
    assert ".main-card" in css
    assert ".step-bar" in css
    assert ".preview-card" in css
    assert ".delivery-card" in css
    assert ".toast" in css


def test_teacher_visual_contract_uses_editorial_studio_layout():
    html = _read_web_file("index.html")
    css = _read_web_file("static/app.css")

    assert "一句话，" in html
    assert "开始今天的备课。" in html
    assert "把格式留给模板" in html
    assert "studio-sidebar" in html
    assert "paper-coral.png" in html
    assert "paper-sage.png" in html
    assert "width: min(1180px" in css
    assert "grid-template-columns: minmax(0, 720px) minmax(300px, 1fr)" in css
    assert "--serif:" in css
