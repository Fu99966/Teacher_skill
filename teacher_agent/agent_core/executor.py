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

    def _execute_one_node(self, node: GraphNode, state: AgentRunState) -> bool:
        """Execute a single graph node. Returns False if failed (critical)."""
        if node.status == "blocked":
            return False
        if node.status in ("done", "paused"):
            return True  # skip already-completed nodes

        state.trace.append({"node": node.id, "label": node.label, "status": "running"})
        state.current_node = node.id

        try:
            node.status = "running"

            # Gate node: pause
            if node.is_gate:
                node.status = "paused"
                node.detail = "等待老师确认教案内容并修改。"
                state.status = "waiting_teacher_review"
                state.next_action = "teacher_edit_fields"
                state.trace[-1]["status"] = "paused"
                self._save_checkpoint(state)
                return True  # success, but paused

            # Context check
            missing = self.registry.check_context(node.tool, {"state": state})
            if missing:
                node.status = "error"
                node.detail = f"缺少上下文: {', '.join(missing)}"
                state.errors.append(node.detail)
                state.trace[-1]["status"] = "error"
                self._save_checkpoint(state)
                return False

            # Execute
            tool_fn = self.registry.get(node.tool)
            result = tool_fn({"state": state})
            node.status = "done"
            node.detail = _compact_detail(result)
            state.trace[-1]["status"] = "done"

            # ── Post-execution: check produced_context_keys ──
            missing_produced = self.registry.validate_produced(node.tool, {"state": state})
            if missing_produced:
                state.warnings.append(
                    f"工具 {node.tool} 执行后缺少产出: {', '.join(missing_produced)}"
                )

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
                    return True
                except Exception as retry_exc:
                    error_msg = str(retry_exc)

            node.status = "error"
            node.detail = error_msg
            state.errors.append(f"{node.label}: {error_msg}")
            state.trace[-1]["status"] = "error"

            if spec is None or spec.critical:
                self._save_checkpoint(state)
                return False

        self._save_checkpoint(state)
        return True

    def run(self, graph: list[GraphNode], state: AgentRunState) -> AgentExecutionResult:
        """Execute a graph, pausing at gate nodes. Checkpoints after each step."""
        failed = False
        for node in graph:
            ok = self._execute_one_node(node, state)
            if not ok:
                failed = True
                break
            if node.is_gate and node.status == "paused":
                # Paused at gate — return early
                return AgentExecutionResult(
                    session_id=state.session_id,
                    status="waiting_teacher_review",
                    next_action="teacher_edit_fields",
                    state=state,
                    failed=False,
                )

        final_status = "failed" if failed else "completed"
        state.status = final_status

        # Auto-repair if failed — try to continue from export_docx
        if failed and state.retry_count < state.max_retries:
            from .repair import repair_state
            state = repair_state(state)
            if state.status == "fields_generated":
                export_idx = _find_node_index(graph, "export_docx")
                if export_idx is not None:
                    result = self.run_from_node(graph, state, export_idx)
                    self._save_checkpoint(state)
                    return result

        self._save_checkpoint(state)
        return AgentExecutionResult(
            session_id=state.session_id,
            status=state.status,
            next_action=state.next_action or "done",
            state=state,
            failed=(state.status == "failed"),
        )

    def continue_after_review(self, graph: list[GraphNode], state: AgentRunState) -> AgentExecutionResult:
        """Resume execution after teacher_review_gate.

        Finds the gate node and executes everything after it.
        Works with freshly-built graphs (node.status is 'pending', not 'paused').
        """
        gate_idx = _find_gate_index(graph)
        if gate_idx is None:
            raise ValueError("No teacher_review_gate found in graph.")

        # Mark all nodes before and including gate as done
        for i in range(gate_idx + 1):
            if graph[i].status == "pending":
                graph[i].status = "done"

        # Execute remaining nodes after gate
        return self.run_from_node(graph, state, gate_idx + 1)

    def run_from_node(self, graph: list[GraphNode], state: AgentRunState, start_idx: int) -> AgentExecutionResult:
        """Execute graph from a specific node index, skipping earlier nodes."""
        failed = False
        for i in range(start_idx, len(graph)):
            ok = self._execute_one_node(graph[i], state)
            if not ok:
                failed = True
                break

        final_status = "failed" if failed else "completed"
        state.status = final_status

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

    # ── Legacy compat ──
    def continue_from_gate(self, group: list[GraphNode], state: AgentRunState) -> AgentExecutionResult:
        """Legacy method — delegates to continue_after_review for robustness."""
        return self.continue_after_review(group, state)

    def _save_checkpoint(self, state: AgentRunState) -> None:
        if self.checkpoint is not None:
            try:
                self.checkpoint.save(state)
            except Exception:
                pass


def _find_gate_index(graph: list[GraphNode]) -> int | None:
    """Return the index of the teacher_review_gate node, or None."""
    for i, node in enumerate(graph):
        if node.is_gate:
            return i
    return None


def _find_node_index(graph: list[GraphNode], node_id: str) -> int | None:
    """Return the index of a node by its id, or None."""
    for i, node in enumerate(graph):
        if node.id == node_id:
            return i
    return None


def _compact_detail(result: dict[str, Any]) -> str:
    parts = []
    for key, value in result.items():
        if value is None:
            continue
        if key == "state":
            continue
        parts.append(f"{key}: {value}")
    return "；".join(parts) if parts else "完成"
