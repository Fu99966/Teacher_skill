from __future__ import annotations

import pytest

from test_stm32_smart_car_prompt_generation import _run_export


def test_delivery_page_exposes_data_driven_word_quality_health():
    html = open("web/index.html", encoding="utf-8").read()
    script = open("web/static/app.js", encoding="utf-8").read()

    assert "Word 质量体检" in html
    assert 'id="word-quality-health"' in html
    assert "output_quality_report" in script
    assert "renderWordQualityHealth" in script


@pytest.mark.parametrize("template_mode", ["system", "upload"])
def test_final_docx_returns_passing_output_quality_report(monkeypatch, tmp_path, template_mode):
    output_path, export = _run_export(
        monkeypatch,
        tmp_path,
        template_mode=template_mode,
        repeat_fill_mode="first_only" if template_mode == "upload" else None,
    )

    assert output_path.exists()
    report = export["output_quality_report"]
    assert report["passed"] is True, report
    assert report["score"] >= 85, report
    assert report["checks"]["no_prompt_leak"] is True
    assert report["checks"]["no_unnamed_title"] is True
    assert report["checks"]["punctuation_clean"] is True
    assert report["checks"]["teaching_method_written"] is True

    if template_mode == "upload":
        assert report["checks"]["teaching_method_fit_for_narrow_cell"] is True
        assert report["checks"]["duplicate_first_only_preserved"] is True
