"""Tests using the real 教案模板.docx fixture."""
from __future__ import annotations

from pathlib import Path

from docx import Document

from teacher_agent.docx_filler import fill_docx_template
from teacher_agent.template_parser import analyze_template

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
REAL_TEMPLATE = FIXTURE_DIR / "教案模板.docx"


def _extract_all_text(docx_path: Path) -> str:
    """Extract all text from a docx file (paragraphs + tables)."""
    doc = Document(str(docx_path))
    parts: list[str] = []
    for p in doc.paragraphs:
        if p.text.strip():
            parts.append(p.text)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                t = cell.text.strip()
                if t:
                    parts.append(t)
    return "\n".join(parts)


# ── Test 1: Real template field detection ──────────────────────────────

def test_real_template_fields_are_detected():
    analysis = analyze_template(REAL_TEMPLATE)
    fields = analysis["mapped_fields"]

    assert "lesson_title" in fields, f"Missing lesson_title in fields: {fields}"
    assert "teaching_goals" in fields, f"Missing teaching_goals in fields: {fields}"
    assert "teaching_key_difficult" in fields, f"Missing teaching_key_difficult in fields: {fields}"
    assert "teaching_process" in fields, f"Missing teaching_process in fields: {fields}"
    assert "teaching_method" in fields, f"Missing teaching_method in fields: {fields}"
    assert "homework" in fields, f"Missing homework in fields: {fields}"
    assert "reflection" not in fields, f"reflection should NOT be in plain table (our template has no 课后小记): {fields}"
    # Actually our template has 作业 but not 课后小记. reflection may be detected from "课后小记" - our template doesn't have it.
    # Let's check what we actually have
    print(f"\nDetected fields: {fields}")

    assert analysis["fillable_count"] > 0
    assert not analysis["needs_template_markers"]


# ── Test 2: 主要教学内容 is NOT lesson_title ───────────────────────────

def test_main_teaching_content_is_not_lesson_title():
    analysis = analyze_template(REAL_TEMPLATE)

    lesson_mappings = analysis["table_mappings"].get("lesson_title", [])
    labels = [
        m.get("label", "").replace(" ", "").replace("\n", "")
        for m in lesson_mappings
    ]

    assert "主要教学内容" not in labels, (
        f"'主要教学内容' should NOT be in lesson_title labels, got: {labels}"
    )

    # Verify it IS in teaching_process
    process_mappings = analysis["table_mappings"].get("teaching_process", [])
    process_labels = [
        m.get("label", "").replace(" ", "").replace("\n", "")
        for m in process_mappings
    ]
    assert any(lbl == "主要教学内容" for lbl in process_labels), (
        f"'主要教学内容' should be in teaching_process labels, got: {process_labels}"
    )


# ── Test 3: Fixed fields are written to real template ──────────────────

def test_fixed_fields_write_to_real_template(tmp_path):
    output_path = tmp_path / "output.docx"
    fields = {
        "授课日期": "2026年5月29日",
        "grade": "24物联网1班",
        "lesson_title": "传感器基础",
        "授课类型": "新授课",
        "class_hour": "2课时",
        "teaching_environment": "多媒体教室，具备投影设备和传感器演示套件。",
        "teaching_goals": "理解传感器的基本概念、分类和典型应用。",
        "teaching_key_difficult": "重点：传感器分类与工作原理。难点：传感器信号与物联网系统的关系。",
        "teaching_aids": "PPT、传感器实物、实验演示板。",
        "teaching_process": "一、导入：展示智能家居传感器案例。\n二、新授：讲解传感器概念、分类与应用。\n三、实践：学生观察传感器模块并分析功能。\n四、总结：梳理传感器在物联网中的作用。",
        "teaching_method": "案例教学、任务驱动、小组讨论、实物演示。",
        "homework": "完成传感器分类表，并举出三个生活中的传感器应用案例。",
        "reflection": "课后关注学生是否能把传感器与物联网应用场景建立联系。",
    }

    report = fill_docx_template(REAL_TEMPLATE, fields, output_path)
    output_text = _extract_all_text(output_path)

    print(f"\nFill report: filled={report.filled_fields}, errors={report.errors}")
    print(f"Output text preview: {output_text[:300]}")

    # Must contain these key texts
    assert "传感器基础" in output_text, f"Output missing '传感器基础': {output_text[:200]}"
    assert "理解传感器的基本概念" in output_text, f"Output missing teaching_goals content"
    assert "案例教学" in output_text, f"Output missing teaching_method content"
    assert "完成传感器分类表" in output_text, f"Output missing homework content"

    # Report checks
    assert "lesson_title" in report.filled_fields
    assert report.filled_non_empty_count > 0
    assert not report.errors, f"Unexpected errors: {report.errors}"


# ── Test 4: Duplicate table writing ────────────────────────────────────

def test_duplicate_tables_get_filled(tmp_path):
    """Our template has 2 tables, both with 课题, so 传感器基础 should appear at least twice."""
    output_path = tmp_path / "output_dup.docx"
    fields = {
        "lesson_title": "传感器基础",
        "teaching_goals": "理解传感器的基本概念",
        "teaching_key_difficult": "重点：分类。难点：信号关系。",
        "teaching_process": "导入→新授→实践→总结",
        "teaching_method": "案例教学法",
        "homework": "完成练习题",
        "teaching_environment": "多媒体教室",
        "teaching_aids": "PPT课件",
        "class_hour": "2课时",
    }

    report = fill_docx_template(REAL_TEMPLATE, fields, output_path)
    output_text = _extract_all_text(output_path)

    # 传感器基础 should appear at least 2 times (one per table)
    count = output_text.count("传感器基础")
    print(f"\n'传感器基础' appears {count} times in output")
    assert count >= 2, f"Expected '传感器基础' at least 2 times, got {count}"

    # Check fill report
    assert "lesson_title" in report.table_fields_filled
    assert report.table_write_count >= 2, f"Expected table_write_count >= 2, got {report.table_write_count}"


# ── Test 5: Next-row fill for 主要教学内容/教学方法的运用 ─────────────

def test_next_row_fill_for_teaching_content_and_method(tmp_path):
    """主要教学内容 and 教学方法的运用 should write to the next row's blank cells."""
    analysis = analyze_template(REAL_TEMPLATE)
    process_mappings = analysis["table_mappings"].get("teaching_process", [])
    method_mappings = analysis["table_mappings"].get("teaching_method", [])

    # At least one of these should target a row different from label row
    process_next_row = any(m.get("label_row") != m.get("row") for m in process_mappings)
    method_next_row = any(m.get("label_row") != m.get("row") for m in method_mappings)

    print(f"\nteaching_process mappings: {len(process_mappings)} targets")
    for m in process_mappings:
        print(f"  label_row={m.get('label_row')}, target_row={m.get('row')}, table={m.get('table')}")
    print(f"teaching_method mappings: {len(method_mappings)} targets")
    for m in method_mappings:
        print(f"  label_row={m.get('label_row')}, target_row={m.get('row')}, table={m.get('table')}")

    assert process_next_row or method_next_row, (
        "Expected next-row fill for 主要教学内容 or 教学方法的运用"
    )

    # Now verify with actual fill
    output_path = tmp_path / "output_next_row.docx"
    fields = {
        "lesson_title": "测试课题",
        "teaching_process": "这是教学过程内容",
        "teaching_method": "案例教学法",
        "teaching_goals": "测试目标",
        "teaching_key_difficult": "测试重难点",
        "homework": "测试作业",
    }
    report = fill_docx_template(REAL_TEMPLATE, fields, output_path)
    output_text = _extract_all_text(output_path)

    print(f"\nFill report: filled={report.filled_fields}, table_write_count={report.table_write_count}")
    assert "这是教学过程内容" in output_text, f"teaching_process content not found: {output_text[:200]}"
    assert "案例教学法" in output_text, f"teaching_method content not found: {output_text[:200]}"


# ── Test 6: Blank template error ────────────────────────────────────────

def test_blank_output_is_rejected():
    """If we provide all-empty fields, system must report error."""
    fields = {
        "lesson_title": "",
        "teaching_goals": "",
        "teaching_key_difficult": "",
        "teaching_process": "",
        "teaching_method": "",
        "homework": "",
    }
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        output_path = Path(f.name)

    try:
        report = fill_docx_template(REAL_TEMPLATE, fields, output_path)
        assert report.errors, f"Expected errors for blank output, got: {report.to_dict()}"
        assert "空白模板" in report.errors[0] or report.filled_non_empty_count == 0
    finally:
        if output_path.exists():
            output_path.unlink()
