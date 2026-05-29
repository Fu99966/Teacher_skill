from __future__ import annotations

import argparse

from docx import Document

from teacher_agent import cli


def test_cli_fill_template_outputs_report(tmp_path, capsys):
    template = tmp_path / "template.docx"
    data = tmp_path / "data.json"
    output = tmp_path / "out.docx"
    document = Document()
    document.add_paragraph("{{lesson_title}}")
    document.save(template)
    data.write_text('{"lesson_title": "桂林山水"}', encoding="utf-8")

    cli.cmd_fill_template(argparse.Namespace(template=str(template), data=str(data), output=str(output)))
    captured = capsys.readouterr().out

    assert "fill_report" in captured
    assert '"success": true' in captured
    assert Document(output).paragraphs[0].text == "桂林山水"


def test_cli_generate_uses_fallback_and_fills_word(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: False)
    template = tmp_path / "template.docx"
    material = tmp_path / "material.md"
    output = tmp_path / "out.docx"
    document = Document()
    document.add_paragraph("{{lesson_title}}")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "教学目标"
    table.cell(0, 1).text = ""
    document.save(template)
    material.write_text("教材内容", encoding="utf-8")

    args = argparse.Namespace(
        template=str(template),
        subject="语文",
        grade="四年级",
        title="桂林山水",
        material_file=str(material),
        output=str(output),
        class_hour="1课时",
        class_type="新授课",
        teaching_style="常规启发式",
        student_level="常规混合水平",
        generation_depth="标准",
        strict_ai=False,
    )
    cli.cmd_generate(args)
    captured = capsys.readouterr().out

    assert '"generation_backend": "local_fallback"' in captured
    assert '"success": true' in captured
    assert Document(output).paragraphs[0].text == "桂林山水"
    assert Document(output).tables[0].cell(0, 1).text
