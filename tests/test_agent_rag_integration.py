from __future__ import annotations

from pathlib import Path

from teacher_agent.agent_core.state import AgentRunState
from teacher_agent.agent_core.tool_registry import build_agent_tool_registry
from teacher_agent.rag_context import MAX_DIRECT_MATERIAL_CHARS, build_knowledge_context


def test_long_material_is_condensed_to_selected_chunks():
    relevant = "课程标准要求学生掌握传感器分类、实验步骤和评价要求。"
    filler = "这是一段不应完整进入生成提示词的普通背景材料。" * 500
    material = relevant + "\n\n" + filler

    context = build_knowledge_context(
        material,
        subject="物联网",
        title="传感器基础",
        class_type="实验课",
        teaching_style="探究式",
    )
    enhanced = context.enhanced_material(material)

    assert len(material) > MAX_DIRECT_MATERIAL_CHARS
    assert "课程标准要求学生掌握传感器分类、实验步骤和评价要求" in enhanced
    assert material not in enhanced
    assert "材料较长，已提取重点片段" in enhanced
    assert len(enhanced) < len(material)


def test_short_material_is_kept_in_enhanced_context():
    material = "教材重点：理解 MQTT 发布订阅机制，并比较 QoS 0、1、2。"
    context = build_knowledge_context(
        material,
        subject="物联网",
        title="MQTT 通信基础",
        class_type="新授课",
        teaching_style="常规启发式",
    )

    assert material in context.enhanced_material(material)


def test_agent_draft_tool_uses_bounded_knowledge_context(monkeypatch, tmp_path: Path):
    captured: dict[str, object] = {}

    def fake_draft(*args, **kwargs):
        captured.update(kwargs)
        return {
            "lesson_title": "传感器基础",
            "teaching_process": "围绕传感器分类开展实验探究。",
            "teaching_method": "探究式教学法。",
        }, "local_fallback"

    monkeypatch.setattr(
        "teacher_agent.lesson_generator.draft_lesson_document_fields_with_source",
        fake_draft,
    )
    material = "课程标准要求学生掌握传感器分类和实验评价。" + ("普通背景材料。" * 3000)
    state = AgentRunState(
        session_id="rag-agent",
        status="initialized",
        task={
            "subject": "物联网",
            "grade": "24级物联网班",
            "title": "传感器基础",
            "material": material,
            "class_hour": "2课时",
            "class_type": "实验课",
            "teaching_style": "探究式",
            "student_level": "常规混合水平",
            "generation_depth": "标准",
            "strict_ai": False,
        },
        current_node="draft_fields",
        next_action="",
        template_analysis={
            "mapped_fields": ["lesson_title", "teaching_process", "teaching_method"],
            "field_context": {},
        },
    )
    registry = build_agent_tool_registry(
        output_dir=tmp_path / "outputs",
        preview_dir=tmp_path / "previews",
        history_db=tmp_path / "history.sqlite3",
        memory_db=tmp_path / "memory.sqlite3",
    )

    result = registry.get("draft_fields")({"state": state})

    enhanced = str(captured["material"])
    assert material not in enhanced
    assert "传感器分类" in enhanced
    assert result["knowledge_chunk_count"] > 0
    assert result["lesson_pattern"] == "experiment_lesson"
    assert state.task["_knowledge_summary"]
    assert state.task["_knowledge_chunk_count"] == result["knowledge_chunk_count"]


def test_agent_run_web_response_exposes_knowledge_diagnostics():
    source = Path("teacher_agent/web_app.py").read_text(encoding="utf-8")

    assert '"knowledge_summary": result.state.task.get("_knowledge_summary", "")' in source
    assert '"knowledge_chunk_count": result.state.task.get("_knowledge_chunk_count", 0)' in source
    assert '"lesson_pattern": result.state.task.get("_lesson_pattern", "")' in source
    assert '"repair_summary": repair_summary' in source
    assert '"repair_actions": repair_actions' in source
    assert '"memory_examples_used": memory_examples_used' in source
    assert '"memory_fields_reused": memory_fields_reused' in source
