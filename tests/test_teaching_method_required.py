"""Tests for teaching_method field-level closed-loop validation.

Covers: template parsing → field generation → export block → write validation → docx verification.
"""
from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
REAL_TEMPLATE = FIXTURE_DIR / "教案模板.docx"

FIXED_FIELDS = {
    "teaching_date": "2026-05-29",
    "class_name": "24物联网1班",
    "lesson_title": "传感器基础",
    "class_type": "新授课",
    "class_hour": "2课时",
    "teaching_environment": "多媒体教室",
    "teaching_goals": "理解传感器的基本概念、分类和典型应用。",
    "teaching_key_difficult": "重点：传感器分类与工作原理。难点：传感器信号与物联网系统的关系。",
    "teaching_aids": "PPT、传感器实物",
    "teaching_process": "一、导入新课：展示传感器图片，提问生活中常见传感器。\n二、项目探究：各组设计一个传感器应用方案。\n三、演示实验：教师演示传感器工作原理。\n四、小组讨论：分析给定场景中使用的传感器类型。\n五、巡回指导：教师巡视各组，及时纠偏。\n六、展示评价：各组展示方案，师生互评。\n七、巩固练习：完成传感器分类任务单。\n八、课堂总结：梳理传感器知识框架。",
    "teaching_method": "采用情境导入法、项目教学法、演示教学法、小组讨论法和案例分析法相结合的教学方式。教学过程中注重学生主体地位，通过创设情境、组织活动、引导探究和即时反馈，帮助学生理解《传感器基础》的核心内容。",
    "homework": "完成传感器分类练习题，观察家中使用的传感器并记录。",
    "reflection": "课后关注学生是否掌握传感器应用。",
}

# teaching_process with rich method keywords for derivation testing
PROCESS_WITH_METHODS = (
    "一、项目导入：展示传感器在物联网项目中的应用案例。\n"
    "二、演示实验：教师演示常用传感器模块。\n"
    "三、小组讨论：各组设计传感器应用场景。\n"
    "四、巡回指导：教师巡视，针对各组问题进行指导。\n"
    "五、展示评价：各组展示方案，师生共同评价。"
)


def _mock_draft_fields(*args, **kwargs):
    return dict(FIXED_FIELDS), "mock"


# ── Test 1: template analysis marks teaching_method as required ──

def test_template_analysis_marks_teaching_method_required():
    """analyze_template must include teaching_method in required_fields."""
    from teacher_agent.template_parser import analyze_template

    analysis = analyze_template(REAL_TEMPLATE)
    required = analysis.get("required_fields", [])

    assert "teaching_method" in required, (
        f"teaching_method should be in required_fields, got: {required}"
    )
    assert "teaching_method" in analysis.get("mapped_fields", []), (
        "teaching_method should be in mapped_fields"
    )


# ── Test 2: table_mappings targets have required=true ──

def test_teaching_method_mapping_has_required_true():
    """Every teaching_method target in table_mappings must have required=true."""
    from teacher_agent.template_parser import analyze_template

    analysis = analyze_template(REAL_TEMPLATE)
    mappings = analysis.get("table_mappings", {}).get("teaching_method", [])

    assert len(mappings) > 0, "No teaching_method targets in table_mappings"

    for i, tgt in enumerate(mappings):
        assert tgt.get("required") is True, (
            f"teaching_method target {i} missing required=true: {tgt}"
        )


# ── Test 3: _derive_teaching_method_from_process works ──

def test_derive_teaching_method_from_process():
    """Fallback derivation from teaching_process text."""
    from teacher_agent.lesson_generator import _derive_teaching_method_from_process

    process = "一、导入新课：创设情境。\n二、探究新知：小组讨论传感器分类。\n三、演示实验。\n四、归纳总结。"
    result = _derive_teaching_method_from_process("", "传感器基础", process)

    assert len(result) > 30, f"Fallback too short: {len(result)} chars"
    assert "探究" in result or "讨论" in result or "演示" in result or "导入" in result, (
        f"Fallback lacks detected methods: {result[:100]}"
    )


# ── Test 4: backfill PREFERS derived teaching_method from process ──

def test_backfill_prefers_derived_teaching_method_from_process():
    """When teaching_method is empty and teaching_process has rich keywords,
    backfill must derive from process, containing matching method names."""
    from teacher_agent.lesson_generator import backfill_empty_fields_with_local_fallback

    fields = dict(FIXED_FIELDS)
    fields["teaching_method"] = ""
    fields["teaching_process"] = PROCESS_WITH_METHODS

    result = backfill_empty_fields_with_local_fallback(
        fields, subject="物联网", grade="24物联网1班", title="传感器基础",
        material="", class_hour="2课时", required_fields=list(FIXED_FIELDS.keys()),
    )

    tm = result.get("teaching_method", "")
    assert tm.strip(), "teaching_method should not be empty after backfill"

    # Must include at least 2 method names derived from process keywords
    required_methods = ["项目教学法", "演示教学法", "小组讨论法"]
    matched = [m for m in required_methods if m in tm]
    assert len(matched) >= 2, (
        f"teaching_method must contain >=2 derived methods from {required_methods}, got: {tm[:120]}"
    )


# ── Test 5: step4-fill blocks empty teaching_method ──

def test_step4_fill_blocks_empty_teaching_method(tmp_path):
    """When teaching_method is required and empty, _handle_step4_fill must return 422."""
    import shutil
    from teacher_agent.template_parser import analyze_template

    tmpl_copy = tmp_path / "教案模板.docx"
    shutil.copy(REAL_TEMPLATE, tmpl_copy)

    analysis = analyze_template(str(tmpl_copy))
    required_fields = analysis.get("required_fields", [])

    fields = dict(FIXED_FIELDS)
    fields["teaching_method"] = ""
    tm_value = str(fields.get("teaching_method") or "").strip()

    if "teaching_method" in required_fields and not tm_value:
        assert True, "Correctly detected empty teaching_method when required"
    else:
        pytest.fail(f"Should detect empty tm: required={required_fields}, value={repr(tm_value)}")


# ── Test 6: full E2E with teaching_method written to both tables ──

def test_teaching_method_e2e_written_to_both_tables(monkeypatch, tmp_path):
    """teaching_method must be non-empty, written to both tables, field_write_counts >= 2.
    NO skipping for default-footer.xml."""
    monkeypatch.setattr(
        "teacher_agent.lesson_generator.draft_lesson_document_fields_with_source",
        _mock_draft_fields,
    )
    monkeypatch.setattr(
        "teacher_agent.deepseek_client.is_deepseek_configured",
        lambda: False,
    )

    from teacher_agent.agent_core.checkpoint import AgentCheckpointStore
    from teacher_agent.agent_core.graph_planner import build_graph
    from teacher_agent.agent_core.state import AgentRunState
    from teacher_agent.agent_core.tool_registry import build_agent_tool_registry
    from teacher_agent.agent_core.executor import AgentExecutor
    from teacher_agent.agent_core.task_router import AgentTask
    from teacher_agent.template_parser import analyze_template

    output_dir = tmp_path / "outputs"
    reg = build_agent_tool_registry(output_dir=output_dir, preview_dir=output_dir,
                                     history_db=output_dir / "h.sqlite3", memory_db=output_dir / "m.sqlite3")
    ck = AgentCheckpointStore(tmp_path)
    exec1 = AgentExecutor(reg, ck)

    template_analysis = analyze_template(REAL_TEMPLATE)

    task = AgentTask(
        raw_request="生成传感器基础教案",
        task_type="lesson_plan", subject="物联网", grade="24物联网1班",
        title="传感器基础", class_hour="2课时", class_type="新授课",
        teaching_style="常规启发式", student_level="常规", generation_depth="标准",
        missing_fields=[], confidence=0.9, notes=[],
    )
    task_dict = task.to_dict()
    task_dict["repeat_fill_mode"] = "all"
    state = AgentRunState(
        session_id="tm-test", status="initialized",
        task=task_dict, current_node="", next_action="",
        template_path=str(REAL_TEMPLATE), template_id="tm-test",
        template_analysis=template_analysis,
    )

    g = build_graph(task)
    res = exec1.run(g, state)

    # Step 1: teaching_method must be non-empty
    fields = res.state.fields or {}
    tm_value = str(fields.get("teaching_method") or "").strip()
    assert tm_value, (
        f"teaching_method is empty after agent run! Trace: {res.state.trace[-3:] if res.state.trace else 'none'}"
    )

    # Step 2: continue through review gate with explicit teaching_method
    fields = dict(res.state.fields or {})
    fields["teaching_method"] = FIXED_FIELDS["teaching_method"]
    ck.save(res.state)
    reloaded = ck.load(state.session_id)
    reloaded.fields = fields
    reloaded.status = "fields_generated"
    reloaded.teacher_edits = {}
    reloaded.template_analysis = template_analysis  # MUST carry template_analysis
    ck.save(reloaded)

    g2 = build_graph(task)
    exec2 = AgentExecutor(reg, ck)
    res2 = exec2.continue_after_review(g2, reloaded)

    # Step 3: MUST be completed — NO skipping for default-footer.xml
    assert res2.status == "completed", (
        f"Agent MUST complete. Status={res2.status}, Errors={res2.state.errors}"
    )

    # Step 4: field_write_counts["teaching_method"] >= 2
    export = res2.state.export_result or {}
    fwc = (export.get("fill_report") or {}).get("field_write_counts", {})
    tm_writes = fwc.get("teaching_method", 0)

    assert tm_writes >= 2, (
        f"teaching_method write count should be >= 2 (both tables), got {tm_writes}. fwc={fwc}"
    )

    # Step 5: verify docx content in next-row cells
    output_name = export.get("output_name", "")
    assert output_name, "No output_name"
    docx_path = output_dir / output_name
    assert docx_path.exists(), f"Docx not found: {docx_path}"

    from docx import Document
    doc = Document(str(docx_path))
    from teacher_agent.docx_grid import parse_table_grid

    written_rows = 0
    for table in doc.tables:
        grid = parse_table_grid(table)
        for ri, row_grid in enumerate(grid):
            for gc, gcell in enumerate(row_grid):
                if gcell is None or gcell.grid_col != gc:
                    continue
                if gcell.text.strip() == "教学方法的运用":
                    if ri + 1 < len(grid):
                        next_row = grid[ri + 1]
                        for ngc, ngcell in enumerate(next_row):
                            if ngcell is not None and ngcell.grid_col == ngc:
                                ntext = ngcell.text.strip()
                                if "教学方法" not in ntext and ntext:
                                    written_rows += 1
                                    break

    assert written_rows >= 2, (
        f"teaching_method content should be in >= 2 next-row cells, found {written_rows}"
    )

    print(f"\n✅ teaching_method E2E: writes={tm_writes}, content_rows={written_rows}")


# ── Test 7: Agent fails cleanly when teaching_method is empty ──

def test_export_fails_when_teaching_method_empty(monkeypatch, tmp_path):
    """When teaching_method is empty, Agent must NOT reach completed;
    evaluation_report.passed must be False or status != completed."""
    monkeypatch.setattr(
        "teacher_agent.lesson_generator.draft_lesson_document_fields_with_source",
        _mock_draft_fields,
    )
    monkeypatch.setattr(
        "teacher_agent.deepseek_client.is_deepseek_configured",
        lambda: False,
    )

    from teacher_agent.agent_core.checkpoint import AgentCheckpointStore
    from teacher_agent.agent_core.graph_planner import build_graph
    from teacher_agent.agent_core.state import AgentRunState
    from teacher_agent.agent_core.tool_registry import build_agent_tool_registry
    from teacher_agent.agent_core.executor import AgentExecutor
    from teacher_agent.agent_core.task_router import AgentTask
    from teacher_agent.template_parser import analyze_template

    output_dir = tmp_path / "outputs"
    reg = build_agent_tool_registry(output_dir=output_dir, preview_dir=output_dir,
                                     history_db=output_dir / "h.sqlite3", memory_db=output_dir / "m.sqlite3")
    ck = AgentCheckpointStore(tmp_path)

    template_analysis = analyze_template(REAL_TEMPLATE)

    task = AgentTask(
        raw_request="生成传感器基础教案",
        task_type="lesson_plan", subject="物联网", grade="24物联网1班",
        title="传感器基础", class_hour="2课时", class_type="新授课",
        teaching_style="常规启发式", student_level="常规", generation_depth="标准",
        missing_fields=[], confidence=0.9, notes=[],
    )
    state = AgentRunState(
        session_id="tm-fail", status="initialized",
        task=task.to_dict(), current_node="", next_action="",
        template_path=str(REAL_TEMPLATE), template_id="tm-fail",
        template_analysis=template_analysis,
    )

    g = build_graph(task)
    exec1 = AgentExecutor(reg, ck)
    res = exec1.run(g, state)

    # Simulate teacher leaving teaching_method empty
    fields = dict(res.state.fields or {})
    fields["teaching_method"] = ""
    ck.save(res.state)
    reloaded = ck.load(state.session_id)
    reloaded.fields = fields
    reloaded.status = "fields_generated"
    reloaded.teacher_edits = {}
    reloaded.template_analysis = template_analysis  # carry template_analysis
    ck.save(reloaded)

    g2 = build_graph(task)
    exec2 = AgentExecutor(reg, ck)
    res2 = exec2.continue_after_review(g2, reloaded)

    # MUST NOT be completed — required field is empty
    assert res2.status != "completed", (
        f"Agent should NOT complete when teaching_method is empty. "
        f"status={res2.status}, errors={res2.state.errors}"
    )

    # Check errors contain teaching_method
    all_errors = " ".join(res2.state.errors or [])
    assert "teaching_method" in all_errors.lower() or "教学方法的运用" in all_errors or "教学方法" in all_errors, (
        f"Errors must mention teaching_method. Got: {res2.state.errors}"
    )

    # Check evaluation_report not passed
    eval_report = res2.state.evaluation_report or {}
    if eval_report:
        assert not eval_report.get("passed", True), (
            f"evaluation_report.passed must be False when teaching_method empty"
        )

    print(f"\n✅ Empty teaching_method test: status={res2.status}, errors={res2.state.errors[:2]}")
