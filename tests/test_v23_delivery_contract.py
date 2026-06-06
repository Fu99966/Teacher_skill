from __future__ import annotations

import inspect
from dataclasses import fields as dataclass_fields
from pathlib import Path

from docx import Document

from teacher_agent.docx_filler import FillReport, fill_docx_template
from teacher_agent.lesson_generator import extract_class_name_from_request
from tests.test_uploaded_template_stm32_teaching_method_cell import (
    _make_complex_template,
    _parallel_heading_cells,
)


def _delivery_fields() -> dict[str, str]:
    return {
        "teaching_date": "2026年6月6日",
        "class_name": "24级物联网班",
        "grade": "24级物联网班",
        "lesson_title": "STM32智能小车课程",
        "subject": "物联网",
        "class_type": "项目实训课",
        "class_hour": "32课时",
        "teaching_environment": "计算机机房和智能小车实训区。",
        "teaching_goals": "掌握GPIO、PWM、电机驱动、循迹和避障控制。",
        "teaching_key_difficult": "重点是PWM与电机驱动，难点是循迹和避障联调。",
        "teaching_aids": "STM32开发板、智能小车、传感器和调试工具。",
        "teaching_process": "本项目共32课时，完成STM32、PWM、电机驱动、循迹和避障任务。",
        "teaching_method": "项目教学法、任务驱动法、巡回指导和作品展示评价。",
        "homework": "整理项目记录。",
        "reflection": "复盘项目实施效果。",
    }


def test_fill_contract_defaults_to_first_only(tmp_path: Path):
    template = _make_complex_template(tmp_path)
    output = tmp_path / "first-only.docx"

    report = fill_docx_template(template, _delivery_fields(), output)
    cells = list(_parallel_heading_cells(Document(str(output))))

    assert report.repeat_fill_mode == "first_only"
    assert report.repeated_sections_detected == 2
    assert report.filled_sections == 1
    assert "STM32" in cells[0][0].text
    assert "项目教学法" in cells[0][1].text
    assert "STM32" not in cells[1][0].text
    assert "项目教学法" not in cells[1][1].text


def test_fill_contract_all_is_explicit(tmp_path: Path):
    template = _make_complex_template(tmp_path)
    output = tmp_path / "all.docx"

    report = fill_docx_template(template, _delivery_fields(), output, repeat_fill_mode="all")
    cells = list(_parallel_heading_cells(Document(str(output))))

    assert report.repeat_fill_mode == "all"
    assert report.filled_sections == 2
    assert all("项目教学法" in method.text for _, method in cells)


def test_repeat_fill_defaults_are_consistent():
    report_field = next(field for field in dataclass_fields(FillReport) if field.name == "repeat_fill_mode")
    signature = inspect.signature(fill_docx_template)

    assert report_field.default == "first_only"
    assert signature.parameters["repeat_fill_mode"].default is None


def test_explicit_class_name_is_preserved():
    request = "帮我生成一份24级物联网班 STM32智能小车课程 32课时的教案。"
    assert extract_class_name_from_request(request) == "24级物联网班"


def test_web_delivery_exposes_template_write_health():
    root = Path(__file__).resolve().parents[1]
    html = (root / "web" / "index.html").read_text(encoding="utf-8")
    js = (root / "web" / "static" / "app.js").read_text(encoding="utf-8")
    css = (root / "web" / "static" / "app.css").read_text(encoding="utf-8")

    assert "模板写入体检" in html
    assert "教学方法的运用未写入模板，请检查模板识别。" in html
    assert "renderTemplateWriteHealth" in js
    assert "field_reports" in js
    assert "written_count" in js
    assert "repeated_sections_detected" in js
    assert "只填第一套" in js
    assert "填充全部" in js
    assert ".template-write-health" in css
