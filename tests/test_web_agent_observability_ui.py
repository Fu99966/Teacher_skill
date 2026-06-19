from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_exposes_teacher_diagnostic_memory_and_material_upload():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")
    css = (ROOT / "web" / "static" / "app.css").read_text(encoding="utf-8")

    assert "一句话生成教案" in html
    assert "material_file" in html
    assert "上传教材资料" in html
    assert "material-extraction-status" in html
    assert "teacher-diagnostic-card" in html
    assert "repair-actions-card" in html
    assert "repair-actions-list" in html
    assert "template-profile-status" in html
    assert "记住这次修改" in html

    assert "/api/remember-edit" in js
    assert "teacher_diagnostic_report" in js
    assert "renderTeacherDiagnostic" in js
    assert "renderMaterialExtractionStatus" in js
    assert "material_extraction" in js
    assert "materialFile" in js
    assert "knowledge_summary" in js
    assert "knowledge_chunk_count" in js
    assert "lesson_pattern" in js
    assert "repair_summary" in js
    assert "repair_actions" in js
    assert "renderRepairActions" in js
    assert "repairActionsCard.hidden = visibleActions.length === 0" in js
    assert "renderTemplateProfileStatus" in js
    assert "current.template_profile" in js
    assert "模板画像：已复用历史成功映射" in js

    assert "teacher-diagnostic-card" in css
    assert "repair-actions" in css
    assert "template-profile-status" in css
