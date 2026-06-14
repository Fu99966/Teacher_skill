from __future__ import annotations

from teacher_agent.agent_core.evaluator import evaluate_pedagogy_quality
from teacher_agent.agent_core.executor import AgentExecutor
from teacher_agent.agent_core.graph_planner import build_graph
from teacher_agent.agent_core.pedagogy_reviser import revise_fields_from_pedagogy_review
from teacher_agent.agent_core.state import AgentRunState
from teacher_agent.agent_core.task_router import AgentTask
from teacher_agent.agent_core.tool_registry import build_agent_tool_registry
from docx import Document


def _weak_fields() -> dict[str, str]:
    return {
        "lesson_title": "传感器基础",
        "subject": "物联网",
        "grade": "24级物联网班",
        "class_hour": "2课时",
        "class_type": "实验课",
        "teaching_goals": "了解知识。",
        "teaching_key_difficult": "传感器。",
        "teaching_process": "讲解传感器。",
        "teaching_method": "讲授。",
        "homework": "做题。",
        "reflection": "以后改进。",
    }


def _task() -> dict[str, str]:
    return {
        "subject": "物联网",
        "grade": "24级物联网班",
        "title": "传感器基础",
        "class_hour": "2课时",
        "class_type": "实验课",
        "material": "课程标准：掌握传感器分类、数据采集和实验评价。",
    }


def test_pedagogy_revision_improves_failed_fields_without_changing_identity():
    fields = _weak_fields()
    before = evaluate_pedagogy_quality(fields, _task())
    assert before["score"] < 60

    revised, changed = revise_fields_from_pedagogy_review(
        fields,
        before,
        _task(),
        allowed_fields=list(fields),
    )
    after = evaluate_pedagogy_quality(revised, _task())

    assert revised["lesson_title"] == "传感器基础"
    assert revised["grade"] == "24级物联网班"
    assert set(changed) >= {
        "teaching_goals",
        "teaching_key_difficult",
        "teaching_process",
        "teaching_method",
        "homework",
        "reflection",
    }
    assert after["score"] > before["score"]
    assert after["passed"] is True


def test_pedagogy_revision_respects_explicit_empty_allowed_fields():
    fields = _weak_fields()
    review = evaluate_pedagogy_quality(fields, _task())

    revised, changed = revise_fields_from_pedagogy_review(
        fields,
        review,
        _task(),
        allowed_fields=[],
    )

    assert revised == fields
    assert changed == []


def test_agent_revise_fields_tool_records_actual_changes(tmp_path):
    fields = _weak_fields()
    state = AgentRunState(
        session_id="pedagogy-revision",
        status="fields_generated",
        task=_task(),
        current_node="revise_fields",
        next_action="",
        fields=fields,
        template_analysis={"mapped_fields": list(fields)},
    )
    state.review_report = evaluate_pedagogy_quality(fields, state.task)

    registry = build_agent_tool_registry(
        output_dir=tmp_path / "outputs",
        preview_dir=tmp_path / "previews",
        history_db=tmp_path / "history.sqlite3",
        memory_db=tmp_path / "memory.sqlite3",
    )
    result = registry.get("revise_fields")({"state": state})

    assert result["revised"] is True
    assert "teaching_process" in result["revised_fields"]
    assert state.review_report["revision"]["changed_fields"] == result["revised_fields"]
    assert state.review_report["revision"]["before_score"] < state.review_report["score"]
    assert state.review_report["revision"]["after_score"] == state.review_report["score"]
    assert state.review_report["passed"] is True


def test_agent_graph_revises_weak_draft_before_teacher_review(monkeypatch, tmp_path):
    template_path = tmp_path / "template.docx"
    document = Document()
    for field in _weak_fields():
        document.add_paragraph("{{" + field + "}}")
    document.save(template_path)

    monkeypatch.setattr(
        "teacher_agent.lesson_generator.draft_lesson_document_fields_with_source",
        lambda *args, **kwargs: (_weak_fields(), "local_fallback"),
    )
    task = AgentTask(
        raw_request="生成24级物联网班传感器基础实验课教案",
        task_type="lesson_plan",
        subject="物联网",
        grade="24级物联网班",
        title="传感器基础",
        class_hour="2课时",
        class_type="实验课",
        teaching_style="探究式",
        student_level="常规混合水平",
        generation_depth="标准",
        missing_fields=[],
        confidence=0.9,
        notes=[],
    )
    state = AgentRunState(
        session_id="pedagogy-graph",
        status="initialized",
        task={**task.to_dict(), "material": _task()["material"]},
        current_node="",
        next_action="",
        template_path=str(template_path),
        template_id="pedagogy-template",
    )
    registry = build_agent_tool_registry(
        output_dir=tmp_path / "outputs",
        preview_dir=tmp_path / "previews",
        history_db=tmp_path / "history.sqlite3",
        memory_db=tmp_path / "memory.sqlite3",
    )

    result = AgentExecutor(registry).run(build_graph(task), state)

    assert result.status == "waiting_teacher_review"
    assert result.state.review_report["passed"] is True
    assert result.state.review_report["revision"]["changed_fields"]
    assert len(result.state.fields["teaching_process"]) > len(_weak_fields()["teaching_process"])
    assert "探究" in result.state.fields["teaching_process"] or "实验" in result.state.fields["teaching_process"]


def test_agent_revision_preserves_teacher_memory_fields(tmp_path):
    fields = _weak_fields()
    remembered_process = "老师确认后的证据链实验过程：观察、记录、解释、互评。"
    fields["teaching_process"] = remembered_process
    state = AgentRunState(
        session_id="pedagogy-memory-protection",
        status="fields_generated",
        task={**_task(), "_memory_fields_reused": ["teaching_process"]},
        current_node="revise_fields",
        next_action="",
        fields=fields,
        template_analysis={"mapped_fields": list(fields)},
    )
    state.review_report = evaluate_pedagogy_quality(fields, state.task)
    registry = build_agent_tool_registry(
        output_dir=tmp_path / "outputs",
        preview_dir=tmp_path / "previews",
        history_db=tmp_path / "history.sqlite3",
        memory_db=tmp_path / "memory.sqlite3",
    )

    result = registry.get("revise_fields")({"state": state})

    assert state.fields["teaching_process"] == remembered_process
    assert "teaching_process" not in result["revised_fields"]
    assert result["revised"] is True
