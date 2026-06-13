from __future__ import annotations

from teacher_agent.agent_core.memory import AgentMemoryStore
from teacher_agent.agent_core.state import AgentRunState
from teacher_agent.agent_core.tool_registry import build_agent_tool_registry
from teacher_agent.lesson_generator import JSON_FIELD_NAMES


def _state(template_id: str, *, title: str = "传感器基础", class_hour: str = "2课时") -> AgentRunState:
    return AgentRunState(
        session_id="memory-loop",
        status="initialized",
        task={
            "raw_text": f"帮我生成一份《{title}》教案",
            "subject": "物联网",
            "grade": "24级物联网班",
            "title": title,
            "class_hour": class_hour,
            "class_type": "实验课",
            "teaching_style": "探究式",
            "student_level": "常规混合水平",
            "generation_depth": "标准",
            "material": "教材重点：传感器分类与数据采集。",
            "strict_ai": False,
        },
        current_node="",
        next_action="",
        template_id=template_id,
        template_analysis={"mapped_fields": list(JSON_FIELD_NAMES), "field_context": {}},
    )


def _registry(tmp_path):
    return build_agent_tool_registry(
        output_dir=tmp_path / "outputs",
        preview_dir=tmp_path / "previews",
        history_db=tmp_path / "history.sqlite3",
        memory_db=tmp_path / "memory.sqlite3",
    )


def test_teacher_edit_memory_uses_prompt_context_not_material(monkeypatch, tmp_path):
    template_id = "school-template.docx"
    memory = AgentMemoryStore(tmp_path / "memory.sqlite3")
    memory.remember_teacher_edit(
        template_id=template_id,
        task={
            "subject": "物联网",
            "grade": "24级物联网班",
            "title": "传感器基础",
            "class_type": "实验课",
        },
        fields={
            "class_hour": "2课时",
            "teaching_process": "老师偏好的证据链实验过程",
            "teaching_method": "问题链驱动法与实验探究法",
        },
    )

    captured = {}

    def fake_draft(**kwargs):
        captured.update(kwargs)
        return (
            {
                "lesson_title": "传感器基础",
                "teaching_process": "新生成过程",
                "teaching_method": "新生成方法",
            },
            "deepseek-test",
        )

    monkeypatch.setattr("teacher_agent.lesson_generator.draft_lesson_document_fields_with_source", fake_draft)
    state = _state(template_id)
    result = _registry(tmp_path).get("draft_fields")({"state": state})

    assert "老师历史修改" not in captured["material"]
    assert "老师偏好的证据链实验过程" in captured["few_shot_examples"]
    assert result["memory_examples_used"] == 1
    assert result["memory_fields_reused"] == []


def test_local_fallback_reuses_exact_teacher_edit_without_overwriting_identity(monkeypatch, tmp_path):
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: False)
    template_id = "school-template.docx"
    memory = AgentMemoryStore(tmp_path / "memory.sqlite3")
    memory.remember_teacher_edit(
        template_id=template_id,
        task={
            "subject": "物联网",
            "grade": "24级物联网班",
            "title": "传感器基础",
            "class_type": "实验课",
        },
        fields={
            "lesson_title": "错误旧课题",
            "grade": "错误旧班级",
            "class_hour": "2课时",
            "teaching_process": "老师确认后的证据链实验过程",
            "teaching_method": "问题链驱动法、实验探究法、同伴互评",
            "homework": "提交传感器数据证据链实验报告。",
        },
    )

    state = _state(template_id)
    result = _registry(tmp_path).get("draft_fields")({"state": state})

    assert result["generation_backend"] == "local_fallback"
    assert set(result["memory_fields_reused"]) >= {"teaching_process", "teaching_method", "homework"}
    assert state.fields["lesson_title"] == "传感器基础"
    assert state.fields["grade"] == "24级物联网班"
    assert state.fields["teaching_process"] == "老师确认后的证据链实验过程"
    assert state.fields["teaching_method"] == "问题链驱动法、实验探究法、同伴互评"
    assert "已复用" in state.warnings[-1]


def test_local_fallback_does_not_reuse_teacher_content_for_different_title(monkeypatch, tmp_path):
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: False)
    template_id = "school-template.docx"
    memory = AgentMemoryStore(tmp_path / "memory.sqlite3")
    memory.remember_teacher_edit(
        template_id=template_id,
        task={
            "subject": "物联网",
            "grade": "24级物联网班",
            "title": "传感器基础",
            "class_type": "实验课",
        },
        fields={
            "class_hour": "2课时",
            "teaching_process": "只属于传感器基础的老师修改内容",
            "teaching_method": "传感器实验专用方法",
        },
    )

    state = _state(template_id, title="物联网通信基础")
    result = _registry(tmp_path).get("draft_fields")({"state": state})

    assert result["generation_backend"] == "local_fallback"
    assert result["memory_examples_used"] == 1
    assert result["memory_fields_reused"] == []
    assert "只属于传感器基础的老师修改内容" not in state.fields["teaching_process"]


def test_teacher_memory_search_ranks_exact_title_first(tmp_path):
    memory = AgentMemoryStore(tmp_path / "memory.sqlite3")
    common_task = {
        "subject": "物联网",
        "grade": "24级物联网班",
        "class_type": "实验课",
    }
    memory.remember_teacher_edit(
        template_id="school-template.docx",
        task={**common_task, "title": "物联网通信基础"},
        fields={"class_hour": "2课时", "teaching_process": "通信课程修改"},
    )
    memory.remember_teacher_edit(
        template_id="school-template.docx",
        task={**common_task, "title": "传感器基础"},
        fields={"class_hour": "2课时", "teaching_process": "传感器课程修改"},
    )

    examples = memory.find_teacher_edit_examples(
        subject="物联网",
        grade="24级物联网班",
        title="传感器基础",
        class_type="实验课",
        template_id="school-template.docx",
        limit=2,
    )

    assert examples[0]["title"] == "传感器基础"
    assert examples[0]["exact_title_match"] is True
    assert examples[0]["match_score"] > examples[1]["match_score"]


def test_local_fallback_does_not_directly_reuse_exact_title_from_other_class_type(monkeypatch, tmp_path):
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: False)
    template_id = "school-template.docx"
    AgentMemoryStore(tmp_path / "memory.sqlite3").remember_teacher_edit(
        template_id=template_id,
        task={
            "subject": "物联网",
            "grade": "24级物联网班",
            "title": "传感器基础",
            "class_type": "实验课",
        },
        fields={
            "class_hour": "2课时",
            "teaching_process": "只适用于实验课的老师修改过程",
            "teaching_method": "实验课专用方法",
        },
    )

    state = _state(template_id)
    state.task["class_type"] = "复习课"
    result = _registry(tmp_path).get("draft_fields")({"state": state})

    assert result["memory_fields_reused"] == []
    assert "只适用于实验课的老师修改过程" not in state.fields["teaching_process"]
