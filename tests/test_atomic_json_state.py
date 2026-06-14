from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

from teacher_agent.agent_core.checkpoint import AgentCheckpointStore
from teacher_agent.agent_core.state import AgentRunState
from teacher_agent.atomic_json import atomic_write_json
from teacher_agent.template_profile import TemplateProfileStore


def _state(index: int) -> AgentRunState:
    return AgentRunState(
        session_id=f"session-{index}",
        status="initialized",
        task={"title": f"并发教案 {index}"},
        current_node="",
        next_action="",
    )


def test_concurrent_checkpoint_saves_preserve_every_session_in_index(tmp_path):
    store = AgentCheckpointStore(tmp_path)

    with ThreadPoolExecutor(max_workers=12) as executor:
        list(executor.map(store.save, (_state(index) for index in range(60))))

    assert set(store.list_recent(limit=100)) == {f"session-{index}" for index in range(60)}
    for index in range(60):
        assert store.load(f"session-{index}") is not None
    json.loads((tmp_path / "agent_sessions" / "_index.json").read_text(encoding="utf-8"))


def test_concurrent_template_profile_updates_leave_valid_profile(tmp_path):
    store = TemplateProfileStore(tmp_path)
    analysis = {
        "mapped_fields": ["lesson_title", "teaching_process", "teaching_method"],
        "table_mappings": {
            "lesson_title": [{"table": 0, "row": 1, "col": 1}],
            "teaching_process": [{"table": 0, "row": 8, "col": 0}],
            "teaching_method": [{"table": 0, "row": 8, "col": 1}],
        },
    }
    profile_id = "学校模板"
    store.get_or_create(profile_id, analysis)

    def update(index: int) -> None:
        store.save_successful_mapping(
            profile_id,
            analysis["table_mappings"],
            {
                "filled_non_empty_count": index + 1,
                "table_write_count": 3,
                "field_write_counts": {"lesson_title": 1, "teaching_process": 1, "teaching_method": 1},
                "repeated_sections_detected": 1,
                "filled_sections": 1,
            },
            mapped_fields=analysis["mapped_fields"],
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(update, range(40)))

    profile_path = store._path(profile_id)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert profile["profile_hit"] is True
    assert profile["mapped_fields"] == analysis["mapped_fields"]
    assert profile["table_mappings"]["teaching_method"]


def test_atomic_write_json_retries_transient_windows_replace_denial(tmp_path, monkeypatch):
    target = tmp_path / "state.json"
    real_replace = os.replace
    attempts = 0

    def transient_replace(source, destination):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(5, "Access is denied")
        real_replace(source, destination)

    monkeypatch.setattr("teacher_agent.atomic_json.os.replace", transient_replace)

    atomic_write_json(target, {"status": "saved"})

    assert attempts == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"status": "saved"}
