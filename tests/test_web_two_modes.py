from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"


def _read_web_file(relative_path: str) -> str:
    return (WEB_ROOT / relative_path).read_text(encoding="utf-8")


def test_web_no_longer_uses_two_mode_homepage():
    html = _read_web_file("index.html")

    assert "一句话生成教案" in html
    assert "使用学校 Word 模板" in html
    assert "按模板填写教案" not in html
    assert "新手模式" not in html
    assert "专业模式" not in html
    assert "智能体框架" not in html


def test_web_keeps_required_template_field_labels():
    js = _read_web_file("static/app.js")

    assert 'teaching_method: "教学方法的运用"' in js
    assert 'teaching_key_difficult: "重点难点"' in js
    assert '{ title: "教学过程与方法", keys: ["teaching_process", "teaching_method"] }' in js
