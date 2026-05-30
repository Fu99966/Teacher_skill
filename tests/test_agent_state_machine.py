"""Tests for AgentRunState state machine."""
from teacher_agent.agent_core.state import AgentRunState, AgentArtifact, STATUS_VALUES, ROUTE_NODES


def test_state_defaults():
    state = AgentRunState(
        session_id="test-1", status="initialized",
        task={"subject": "语文"}, current_node="", next_action="",
    )
    d = state.to_dict()
    assert d["session_id"] == "test-1"
    assert d["status"] == "initialized"
    assert d["fields"] is None
    assert d["errors"] == []
    assert d["trace"] == []
    assert d["retry_count"] == 0


def test_artifact_serialization():
    a = AgentArtifact(name="test", url="/download/x.docx", kind="docx", summary="test file")
    d = a.to_dict()
    assert d["name"] == "test"
    assert d["url"] == "/download/x.docx"
    assert d["kind"] == "docx"


def test_status_values_include_gate():
    assert "waiting_teacher_review" in STATUS_VALUES
    assert "completed" in STATUS_VALUES
    assert "failed" in STATUS_VALUES
    assert "repairing" in STATUS_VALUES


def test_route_nodes_include_gate():
    assert "teacher_review_gate" in ROUTE_NODES
    assert "export_docx" in ROUTE_NODES
    assert "evaluate_delivery" in ROUTE_NODES


def test_state_transitions_preserve_fields():
    state = AgentRunState(
        session_id="test-2", status="initialized",
        task={"subject": "数学"}, current_node="diagnose_template",
        next_action="draft_fields",
        fields={"lesson_title": "测试"},
    )
    state.status = "fields_generated"
    state.fields["teaching_goals"] = "理解概念"
    assert state.status == "fields_generated"
    assert state.fields["lesson_title"] == "测试"
    assert state.fields["teaching_goals"] == "理解概念"
