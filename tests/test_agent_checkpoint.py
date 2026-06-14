"""Tests for AgentCheckpointStore."""
from teacher_agent.agent_core.checkpoint import AgentCheckpointStore
from teacher_agent.agent_core.state import AgentRunState


def test_save_and_load(tmp_path):
    store = AgentCheckpointStore(tmp_path)
    state = AgentRunState(
        session_id="ckpt-1", status="fields_generated",
        task={"subject": "语文"}, current_node="draft_fields",
        next_action="pedagogy_review",
        fields={"lesson_title": "桂林山水"},
    )
    store.save(state)
    loaded = store.load("ckpt-1")
    assert loaded is not None
    assert loaded.session_id == "ckpt-1"
    assert loaded.status == "fields_generated"
    assert loaded.fields["lesson_title"] == "桂林山水"


def test_load_missing_returns_none(tmp_path):
    store = AgentCheckpointStore(tmp_path)
    assert store.load("nonexistent") is None


def test_update_modifies_and_persists(tmp_path):
    store = AgentCheckpointStore(tmp_path)
    state = AgentRunState(
        session_id="ckpt-2", status="initialized",
        task={}, current_node="", next_action="",
    )
    store.save(state)

    updated = store.update("ckpt-2", status="completed", fields={"homework": "写作业"})
    assert updated.status == "completed"
    assert updated.fields["homework"] == "写作业"

    reloaded = store.load("ckpt-2")
    assert reloaded.status == "completed"
    assert reloaded.fields["homework"] == "写作业"


def test_delete_removes_checkpoint(tmp_path):
    store = AgentCheckpointStore(tmp_path)
    state = AgentRunState(
        session_id="ckpt-3", status="initialized",
        task={}, current_node="", next_action="",
    )
    store.save(state)
    assert store.load("ckpt-3") is not None
    store.delete("ckpt-3")
    assert store.load("ckpt-3") is None
    assert "ckpt-3" not in store.list_recent()
