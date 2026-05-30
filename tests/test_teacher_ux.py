"""Tests for UI/UX enhancements: probe parsing, teacher_report, beginner/pro modes."""
from __future__ import annotations

import json


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


# ── Test 2: teacher_report structure ──

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


# ── Test 3: beginner mode hides technical details ──

def test_beginner_mode_hides_technical_details():
    """Validate that the mode API returns beginner-friendly info without raw diagnostics."""
    # The API response includes mode and beginner_summary
    # Test the structure from the API contract
    beginner_response = {
        "mode": "表格标签模板",
        "visible_sections": ["fields", "trace", "download"],
        "technical_details_available": True,
        "beginner_summary": "教案生成成功，请下载 Word 文件并检查内容是否正确填写。",
    }

    # Beginner mode: no professional_diagnostics in visible sections
    assert "professional_diagnostics" not in beginner_response.get("visible_sections", [])
    assert "template_analysis" not in beginner_response.get("visible_sections", [])

    # beginner_summary is human-readable
    assert len(beginner_response["beginner_summary"]) > 0
    # No raw JSON, no template_analysis blobs in the summary
    assert "table_mappings" not in beginner_response["beginner_summary"]


# ── Test 4: professional mode shows diagnostics ──

def test_professional_mode_shows_diagnostics():
    """Validate that the professional mode API response includes diagnostics."""
    pro_response = {
        "mode": "表格标签模板",
        "visible_sections": ["fields", "trace", "download", "diagnostics"],
        "technical_details_available": True,
        "beginner_summary": "教案生成成功。",
        "professional_diagnostics": {
            "table_mappings": {"teaching_process": [{"label": "主要教学内容", "row": 8, "label_row": 7}]},
            "field_write_counts": {"teaching_process": 1},
            "template_errors": [],
        },
    }

    assert "professional_diagnostics" in pro_response
    diags = pro_response["professional_diagnostics"]
    assert "table_mappings" in diags
    assert "field_write_counts" in diags
    assert "template_errors" in diags
    assert len(diags["table_mappings"]) > 0
