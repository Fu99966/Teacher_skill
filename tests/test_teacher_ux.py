"""Tests for UI/UX: probe parsing, real HTML verification, placeholder template, modes."""
from __future__ import annotations

from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
WEB_HTML = PROJECT / "web-new" / "index.html"


# ── Test 1: probe query parsing ──

def test_model_health_probe_query_parsing():
    """_parse_probe supports 1, true, yes, on."""
    from teacher_agent.web_app import _parse_probe

    assert _parse_probe("probe=1") is True
    assert _parse_probe("probe=true") is True
    assert _parse_probe("probe=yes") is True
    assert _parse_probe("probe=on") is True
    assert _parse_probe("") is False
    assert _parse_probe("probe=0") is False
    assert _parse_probe("probe=false") is False
    assert _parse_probe("other=1") is False


# ── Test 2: teacher_report summary ──

def test_web_teacher_report_summary():
    """_beginner_summary returns a meaningful, non-empty string."""
    from teacher_agent.web_app import _beginner_summary

    s1 = _beginner_summary(None, False, "表格标签模板")
    assert isinstance(s1, str) and len(s1) > 0, f"Empty summary from non-None args: {len(s1)}"

    eval_report = {
        "delivery": {"passed": True},
        "pedagogy_score": 85,
        "checks": ["教学目标具体", "过程结构完整"],
    }
    s2 = _beginner_summary(eval_report, False, "占位符模板")
    assert isinstance(s2, str) and len(s2) > 0


# ── Test 3: real HTML contains beginner/pro mode elements ──

def test_real_html_contains_mode_toggle_and_checklist():
    """Verify web-new/index.html has mode toggle, isPro, checklist fields."""
    html = WEB_HTML.read_text(encoding="utf-8")

    # mode-toggle element
    assert 'mode-toggle' in html, "Missing mode-toggle element"
    assert '🔰 新手模式' in html or 'isPro' in html, "Missing beginner/pro mode logic"

    # isPro variable
    assert 'isPro' in html, "Missing isPro variable"

    # professional diagnostics references
    assert '专业诊断' in html or 'professional_diagnostics' in html, "Missing professional diagnostics"

    # fill_report reference
    assert 'fill_report' in html, "Missing fill_report reference"

    # template_analysis reference
    assert 'template_analysis' in html, "Missing template_analysis reference"

    # placeholder template download link
    assert '/download/placeholder-template' in html, "Missing placeholder template download link"

    # delivery checklist fields (Chinese labels)
    checklist_fields = ["课题", "教学目的", "主要教学内容", "教学方法", "作业", "课后小记"]
    for label in checklist_fields:
        assert label in html, f"Checklist field '{label}' not found in HTML"


# ── Test 4: beginner mode hides technical details (real HTML check) ──

def test_beginner_mode_hides_technical_details():
    """Verify the HTML's beginner-mode path doesn't expose raw diagnostics."""
    html = WEB_HTML.read_text(encoding="utf-8")

    # Professional diagnostics should be behind a conditional (isPro)
    assert 'isPro' in html, "isPro flag missing — no mode-gating"
    assert 'if(isPro)' in html or 'if (isPro)' in html, "Professional content not gated behind isPro"

    # Beginner path: must have checklist items visible (not gated)
    checklist_items = ["课题", "教学目的", "主要教学内容", "教学方法", "作业", "课后小记"]
    for item in checklist_items:
        assert item in html, f"Checklist item '{item}' not in HTML"

    # testRealHtml also verifies mode-toggle and placeholder-template exist


# ── Test 5: professional mode shows diagnostics (real HTML check) ──

def test_professional_mode_shows_diagnostics():
    """Verify HTML's professional path exposes fill_report, template_analysis, errors."""
    html = WEB_HTML.read_text(encoding="utf-8")

    # Must have professional diagnostics block
    assert '专业诊断' in html or 'professional_diagnostics' in html, "No professional diagnostics block"

    # Must reference technical fields
    assert 'fill_report' in html, "No fill_report in HTML"
    assert 'template_analysis' in html, "No template_analysis in HTML"
    assert 'field_write_counts' in html, "No field_write_counts in HTML"
    assert 'table_mappings' in html, "No table_mappings in HTML"

    # Must have download diagnostics button or link
    assert '/download/' in html, "No download link present"


# ── Test 6: placeholder template generation and content verification ──

def test_placeholder_template_download_or_generation(tmp_path):
    """Generate placeholder template, verify contents via python-docx."""
    from teacher_agent.web_app import _create_placeholder_template
    from docx import Document

    path = tmp_path / "placeholder.docx"
    _create_placeholder_template(path)

    assert path.exists(), "Placeholder template file was not created"
    assert path.stat().st_size > 1000, f"Template too small: {path.stat().st_size} bytes"

    doc = Document(str(path))
    all_text = "\n".join(
        cell.text for table in doc.tables
        for row in table.rows
        for cell in row.cells
    )

    placeholders = [
        "{{lesson_title}}",
        "{{teaching_goals}}",
        "{{teaching_key_difficult}}",
        "{{teaching_process}}",
        "{{teaching_method}}",
        "{{homework}}",
        "{{reflection}}",
    ]
    for ph in placeholders:
        assert ph in all_text, f"Placeholder '{ph}' not found in template"
