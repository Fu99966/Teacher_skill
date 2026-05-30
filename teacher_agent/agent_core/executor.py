"""AgentExecutor – upgraded with pause, retry, repair, and checkpoint support."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .checkpoint import AgentCheckpointStore
from .graph_planner import GraphNode
from .state import AgentRunState
from .tool_spec import ToolRegistry


@dataclass
class AgentExecutionResult:
    session_id: str
    status: str
    next_action: str
    state: AgentRunState
    failed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "status": self.status,
            "next_action": self.next_action,
            "state": self.state.to_dict(),
            "failed": self.failed,
        }


class AgentExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        checkpoint_store: AgentCheckpointStore | None = None,
    ) -> None:
        self.registry = registry
        self.checkpoint = checkpoint_store

    def run(self, graph: list[GraphNode], state: AgentRunState) -> AgentExecutionResult:
        """Execute a graph, pausing at gate nodes. Checkpoints after each step."""
        failed = False

        for node in graph:
            if node.status == "blocked":
                failed = True
                continue
            if node.status in ("done", "paused"):
                continue  # skip already-completed nodes

            # ── Trace ──
            state.trace.append({
                "node": node.id,
                "label": node.label,
                "status": "running",
            })
            state.current_node = node.id

            try:
                node.status = "running"

                # ── Gate node: pause ──
                if node.is_gate:
                    node.status = "paused"
                    node.detail = "等待老师确认教案内容并修改。"
                    state.status = "waiting_teacher_review"
                    state.next_action = "teacher_edit_fields"
                    state.trace[-1]["status"] = "paused"
                    self._save_checkpoint(state)
                    return AgentExecutionResult(
                        session_id=state.session_id,
                        status="waiting_teacher_review",
                        next_action="teacher_edit_fields",
                        state=state,
                        failed=False,
                    )

                # ── Context check ──
                missing = self.registry.check_context(node.tool, {"state": state})
                if missing:
                    node.status = "error"
                    node.detail = f"缺少上下文: {', '.join(missing)}"
                    state.errors.append(node.detail)
                    failed = True
                    state.trace[-1]["status"] = "error"
                    self._save_checkpoint(state)
                    break

                # ── Execute ──
                tool_fn = self.registry.get(node.tool)
                result = tool_fn({"state": state})
                node.status = "done"
                node.detail = _compact_detail(result)
                state.trace[-1]["status"] = "done"

            except Exception as exc:
                spec = self.registry.get_spec(node.tool)
                retryable = spec.retryable if spec else False
                error_msg = str(exc)

                if retryable and state.retry_count < state.max_retries:
                    state.warnings.append(f"节点 {node.label} 失败，正在重试: {error_msg}")
                    try:
                        result = tool_fn({"state": state})
                        node.status = "done"
                        node.detail = _compact_detail(result)
                        state.trace[-1]["status"] = "done"
                        state.retry_count += 1
                        self._save_checkpoint(state)
                        continue
                    except Exception as retry_exc:
                        error_msg = str(retry_exc)

                node.status = "error"
                node.detail = error_msg
                state.errors.append(f"{node.label}: {error_msg}")
                state.trace[-1]["status"] = "error"
                failed = True
                self._save_checkpoint(state)

                # Critical failure → stop
                if spec is None or spec.critical:
                    break

            self._save_checkpoint(state)

        # ── Final status ──
        final_status = "failed" if failed else "completed"
        state.status = final_status

        # Auto-repair if failed
        if failed and state.retry_count < state.max_retries:
            from .repair import repair_state
            state = repair_state(state)

        self._save_checkpoint(state)
        return AgentExecutionResult(
            session_id=state.session_id,
            status=state.status,
            next_action=state.next_action or "done",
            state=state,
            failed=(state.status == "failed"),
        )

    def continue_from_gate(self, group: list[GraphNode], state: AgentRunState) -> AgentExecutionResult:
        """Resume execution from a teacher_review_gate pause point."""
        gate_idx = None
        for i, node in enumerate(group):
            if node.is_gate and node.status == "paused":
                gate_idx = i
                break

        if gate_idx is None:
            raise ValueError("No paused gate node found – agent is not waiting for teacher review.")

        remaining = group[gate_idx:]  # includes the gate (already paused) + subsequent nodes
        return self.run(remaining, state)

    def _save_checkpoint(self, state: AgentRunState) -> None:
        if self.checkpoint is not None:
            try:
                self.checkpoint.save(state)
            except Exception:
                pass


def _compact_detail(result: dict[str, Any]) -> str:
    parts = []
    for key, value in result.items():
        if value is None:
            continue
        if key == "state":
            continue  # skip full state dump
        parts.append(f"{key}: {value}")
    return "；".join(parts) if parts else "完成"
