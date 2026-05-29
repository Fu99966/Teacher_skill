from __future__ import annotations

from pathlib import Path

from teacher_agent.agent_core.evaluator import evaluate_lesson_output


def test_evaluator_fails_blank_template_risk(tmp_path):
    output = tmp_path / "out.docx"
    output.write_bytes(b"not really a docx")

    report = evaluate_lesson_output(
        fields={"lesson_title": "", "teaching_goals": "", "teaching_process": ""},
        output_path=Path(output),
        download_url="/download/out.docx",
        template_analysis={"mapped_fields": ["lesson_title", "teaching_goals", "teaching_process"]},
        fill_report={
            "filled_non_empty_count": 0,
            "missing_fields": [],
            "remaining_placeholders": [],
            "errors": ["生成失败：检测到输出可能为空白模板，未写入任何非空字段。"],
        },
    )

    assert report.passed is False
    assert any(check.name == "blank_template_precheck" and not check.passed for check in report.checks)
    assert any(check.name == "filled_non_empty_count" and not check.passed for check in report.checks)
