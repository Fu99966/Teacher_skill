"""AgentCheckpointStore – JSON file-based checkpoint persistence."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ..atomic_json import atomic_write_json, json_path_lock, read_json
from .state import AgentArtifact, AgentRunState


class AgentCheckpointStore:
    """Persist and restore AgentRunState using JSON files.

    Checkpoints are stored in {base_dir}/agent_sessions/{session_id}.json
    A lightweight index file tracks recent sessions.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        self.sessions_dir = self.base_dir / "agent_sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        safe = session_id.replace("/", "_").replace("\\", "_")
        return self.sessions_dir / f"{safe}.json"

    def save(self, state: AgentRunState) -> None:
        data = state.to_dict()
        data["_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        atomic_write_json(self._path(state.session_id), data, indent=2)
        self._update_index(state.session_id)

    def load(self, session_id: str) -> AgentRunState | None:
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            data = read_json(path)
        except (json.JSONDecodeError, OSError):
            return None

        artifacts = [
            AgentArtifact(**a) if isinstance(a, dict) else a
            for a in data.get("artifacts", [])
        ]
        data.pop("_updated_at", None)
        return AgentRunState(
            session_id=data.get("session_id", session_id),
            status=data.get("status", "initialized"),
            task=data.get("task", {}),
            current_node=data.get("current_node", ""),
            next_action=data.get("next_action", ""),
            template_path=data.get("template_path"),
            template_id=data.get("template_id"),
            template_analysis=data.get("template_analysis"),
            template_profile=data.get("template_profile"),
            fields=data.get("fields"),
            teacher_edits=data.get("teacher_edits"),
            review_report=data.get("review_report"),
            export_result=data.get("export_result"),
            evaluation_report=data.get("evaluation_report"),
            teacher_report=data.get("teacher_report"),
            artifacts=artifacts,
            trace=data.get("trace", []),
            errors=data.get("errors", []),
            warnings=data.get("warnings", []),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 1),
        )

    def update(self, session_id: str, **patch) -> AgentRunState:
        state = self.load(session_id)
        if state is None:
            raise KeyError(f"Session not found: {session_id}")
        for key, value in patch.items():
            if hasattr(state, key):
                setattr(state, key, value)
        self.save(state)
        return state

    def delete(self, session_id: str) -> None:
        path = self._path(session_id)
        with json_path_lock(path):
            if path.exists():
                os.remove(str(path))
        index_path = self.sessions_dir / "_index.json"
        with json_path_lock(index_path):
            entries = self._read_index(index_path)
            if entries.pop(session_id, None) is not None:
                atomic_write_json(index_path, entries)

    def list_recent(self, limit: int = 10) -> list[str]:
        index_path = self.sessions_dir / "_index.json"
        entries = self._read_index(index_path)
        return [
            session_id
            for session_id, _updated_at in sorted(entries.items(), key=lambda item: item[1], reverse=True)[:limit]
        ]

    def _update_index(self, session_id: str) -> None:
        index_path = self.sessions_dir / "_index.json"
        with json_path_lock(index_path):
            entries = self._read_index(index_path)
            entries[session_id] = f"{time.time_ns():020d}"
            atomic_write_json(index_path, entries)

    @staticmethod
    def _read_index(index_path: Path) -> dict[str, str]:
        try:
            value = read_json(index_path, {})
            return {str(key): str(updated_at) for key, updated_at in value.items()} if isinstance(value, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}
