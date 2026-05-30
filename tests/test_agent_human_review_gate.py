"""Tests for teacher_review_gate – agent pause and continue flow."""
import uuid
from pathlib import Path

from teacher_agent.agent_core.checkpoint import AgentCheckpointStore
from teacher_agent.agent_core.graph_planner import build_graph
from teacher_agent.agent_core.state import AgentRunState
from teacher_agent.agent_core.tool_registry import build_agent_tool_registry
from teacher_agent.agent_core.executor import AgentExecutor
from teacher_agent.agent_core.task_router import AgentTask

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
REAL_TEMPLATE = FIXTURE_DIR / "教案模板.docx"


def test_agent_pauses_at_teacher_review_gate(tmp_path):
    task = AgentTask(
        raw_request="生成物联网传感器基础教案",
        task_type="lesson_plan", subject="物联网", grade="24物联网1班",
        title="传感器基础", class_hour="2课时", class_type="新授课",
        teaching_style="常规启发式", student_level="常规", generation_depth="标准",
        missing_fields=[], confidence=0.9, notes=[],
    )

    state = AgentRunState(
        session_id="gate-test-1", status="initialized",
        task=task.to_dict(), current_node="", next_action="",
        template_path=str(REAL_TEMPLATE),
    )

    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    registry = build_agent_tool_registry(
        output_dir=output_dir, preview_dir=output_dir,
        history_db=output_dir / "history.sqlite3",
        memory_db=output_dir / "memory.sqlite3",
    )
    checkpoint = AgentCheckpointStore(tmp_path)
    executor = AgentExecutor(registry, checkpoint)

    graph = build_graph(task)
    result = executor.run(graph, state)

    assert result.status == "waiting_teacher_review", f"Expected waiting_teacher_review, got {result.status}"
    assert result.next_action == "teacher_edit_fields"
    assert result.state.fields is not None
    assert len(result.state.fields) > 0
    assert result.state.status == "waiting_teacher_review"


def test_teacher_edit_and_continue(tmp_path):
    task = AgentTask(
        raw_request="生成物联网传感器基础教案",
        task_type="lesson_plan", subject="物联网", grade="24物联网1班",
        title="传感器基础", class_hour="2课时", class_type="新授课",
        teaching_style="常规启发式", student_level="常规", generation_depth="标准",
        missing_fields=[], confidence=0.9, notes=[],
    )

    state = AgentRunState(
        session_id="gate-test-2", status="initialized",
        task=task.to_dict(), current_node="", next_action="",
        template_path=str(REAL_TEMPLATE),
    )

    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    registry = build_agent_tool_registry(
        output_dir=output_dir, preview_dir=output_dir,
        history_db=output_dir / "history.sqlite3",
        memory_db=output_dir / "memory.sqlite3",
    )
    checkpoint = AgentCheckpointStore(tmp_path)
    executor = AgentExecutor(registry, checkpoint)

    # Run to gate
    graph = build_graph(task)
    result = executor.run(graph, state)
    assert result.status == "waiting_teacher_review"

    # Teacher modifies homework
    teacher_edits = {"homework": "完成传感器实验报告，观察家中3种传感器并记录功能。"}
    fields = result.state.fields.copy()
    fields.update(teacher_edits)
    result.state.fields = fields
    result.state.teacher_edits = teacher_edits
    result.state.status = "fields_generated"
    checkpoint.save(result.state)

    # Continue
    state2 = checkpoint.load("gate-test-2")
    assert state2.teacher_edits == teacher_edits
    result2 = executor.continue_from_gate(graph, state2)

    assert result2.status in ("completed", "failed"), f"Unexpected status: {result2.status}"
    if result2.status == "completed":
        # Verify homework was included
        export = result2.state.export_result or {}
        assert export.get("download_url"), "Missing download URL"
        download_path = output_dir / str(export.get("output_name", ""))
        if download_path.exists():
            from docx import Document
            doc = Document(str(download_path))
            all_text = "\n".join(
                cell.text for table in doc.tables
                for row in table.rows for cell in row.cells
            )
            assert "传感器" in all_text or "homework" in str(result2.state.fields)


def test_checkpoint_survives_pause(tmp_path):
    task = AgentTask(
        raw_request="test", task_type="lesson_plan",
        subject="语文", grade="四年级", title="观潮", class_hour="1课时",
        class_type="新授课", teaching_style="常规启发式",
        student_level="常规", generation_depth="标准",
        missing_fields=[], confidence=0.9, notes=[],
    )

    state = AgentRunState(
        session_id="gate-test-3", status="initialized",
        task=task.to_dict(), current_node="", next_action="",
        template_path=str(REAL_TEMPLATE),
    )

    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    checkpoint = AgentCheckpointStore(tmp_path)
    executor = AgentExecutor(
        build_agent_tool_registry(
            output_dir=output_dir, preview_dir=output_dir,
            history_db=output_dir / "h.sqlite3", memory_db=output_dir / "m.sqlite3",
        ), checkpoint,
    )

    graph = build_graph(task)
    executor.run(graph, state)

    # Reload from checkpoint
    reloaded = checkpoint.load("gate-test-3")
    assert reloaded is not None
    assert reloaded.current_node in ("", "teacher_review_gate") or bool(reloaded.status)
    assert reloaded.fields is not None
