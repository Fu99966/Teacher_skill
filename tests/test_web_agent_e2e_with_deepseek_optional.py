"""E2E Web Agent test with real DeepSeek — skipped if API key not configured.

Validates the full pipeline with real AI-generated fields:
  agent/start → waiting_teacher_review → continue → completed → verify Word.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from teacher_agent.agent_core.checkpoint import AgentCheckpointStore
from teacher_agent.agent_core.graph_planner import build_graph
from teacher_agent.agent_core.state import AgentRunState
from teacher_agent.agent_core.tool_registry import build_agent_tool_registry
from teacher_agent.agent_core.executor import AgentExecutor
from teacher_agent.agent_core.task_router import AgentTask

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
REAL_TEMPLATE = FIXTURE_DIR / "教案模板.docx"
TEACHER_EDITS = {"homework": "老师修改后的作业内容——DeepSeek生成版。"}


def _make_task():
    return AgentTask(
        raw_request="生成物联网传感器基础教案",
        task_type="lesson_plan", subject="物联网", grade="24物联网1班",
        title="传感器基础", class_hour="2课时", class_type="新授课",
        teaching_style="常规启发式", student_level="常规", generation_depth="标准",
        missing_fields=[], confidence=0.9, notes=[],
    )


def _make_state(template_path, suffix=""):
    tid = f"e2e-ds-{suffix}"
    return AgentRunState(
        session_id=tid, status="initialized",
        task=_make_task().to_dict(), current_node="", next_action="",
        template_path=str(template_path), template_id=tid,
    )


def _make_registry(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    return build_agent_tool_registry(
        output_dir=output_dir, preview_dir=output_dir,
        history_db=output_dir / "h.sqlite3", memory_db=output_dir / "m.sqlite3",
    )


def test_web_agent_e2e_with_deepseek(tmp_path):
    """E2E with real DeepSeek. Requires DEEPSEEK_API_KEY env var."""
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not configured — skipping DeepSeek E2E test")

    output_dir = tmp_path / "outputs"
    checkpoint_dir = tmp_path

    registry = _make_registry(output_dir)
    checkpoint = AgentCheckpointStore(checkpoint_dir)
    executor = AgentExecutor(registry, checkpoint)

    # ── START ──
    state = _make_state(REAL_TEMPLATE, "ds-start")
    graph = build_graph(_make_task())
    result = executor.run(graph, state)

    assert result.status == "waiting_teacher_review", (
        f"DeepSeek E2E start failed: {result.status}. Errors: {result.state.errors}"
    )
    assert result.state.fields is not None, "DeepSeek 未生成 fields"
    fields = result.state.fields or {}
    assert fields.get("lesson_title") or fields.get("teaching_process"), (
        f"DeepSeek 生成 fields 内容不足: {list(fields.keys())[:5]}"
    )

    # ── GET (checkpoint) ──
    reloaded = checkpoint.load(state.session_id)
    assert reloaded is not None, "checkpoint 恢复失败"

    # ── CONTINUE ──
    fields = dict(reloaded.fields or {})
    fields.update(TEACHER_EDITS)
    reloaded.fields = fields
    reloaded.teacher_edits = TEACHER_EDITS
    reloaded.status = "fields_generated"
    checkpoint.save(reloaded)

    new_graph = build_graph(_make_task())
    executor2 = AgentExecutor(registry, checkpoint)
    result2 = executor2.continue_after_review(new_graph, reloaded)

    assert result2.status == "completed", (
        f"DeepSeek continue failed: {result2.status}. Errors: {result2.state.errors}"
    )

    # ── VERIFY Word ──
    export = result2.state.export_result or {}
    output_name = export.get("output_name", "")
    assert output_name, "Word 导出失败"
    docx_path = output_dir / output_name
    assert docx_path.exists(), f"Word 文件不存在: {docx_path}"

    from docx import Document
    doc = Document(str(docx_path))
    all_text = "\n".join(
        cell.text for table in doc.tables
        for row in table.rows for cell in row.cells
    )

    checks = [
        ("传感器基础", "课题名称"),
        ("老师修改后的作业内容——DeepSeek生成版", "老师编辑后的作业"),
    ]
    for keyword, label in checks:
        assert keyword in all_text, (
            f"DeepSeek E2E 内容验证失败：「{label}」({keyword}) 不在输出中。\n"
            f"前500字：{all_text[:500]}"
        )

    # ── Position verification from template_analysis ──
    analysis = result2.state.template_analysis or {}
    for f, label_text in [("teaching_process", "主要教学内容"), ("teaching_method", "教学方法的运用")]:
        targets = analysis.get("table_mappings", {}).get(f, [])
        for t in targets:
            if t.get("label", "").replace(" ", "").replace("\n", "") == label_text:
                assert t["row"] > t["label_row"], (
                    f"DeepSeek E2E：{f} target_row({t['row']}) must be > label_row({t['label_row']})"
                )
                assert t.get("target_type") == "next_row_cell", (
                    f"DeepSeek E2E：{f} target_type={t.get('target_type')}, expected next_row_cell"
                )

    print(f"\n✅ DeepSeek E2E PASS: fields_count={len(fields)}, output={output_name}")
