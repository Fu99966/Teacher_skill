"""Graph-based planner with branching nodes including teacher_review_gate pause point."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .state import ROUTE_NODES
from .task_router import AgentTask


@dataclass
class GraphNode:
    id: str
    tool: str
    label: str
    status: str = "pending"
    detail: str = ""
    is_gate: bool = False  # True = teacher_review_gate pause point

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_graph(task: AgentTask) -> list[GraphNode]:
    """Build a branching execution graph for a lesson plan task.

    The graph includes teacher_review_gate as a mandatory pause point.
    Other task types get an unsupported block.
    """
    if task.task_type != "lesson_plan":
        return [
            GraphNode(
                id="unsupported_task", tool="none",
                label="暂不支持的任务",
                status="blocked",
                detail=f"当前只支持 lesson_plan，识别到 {task.task_type}。",
            )
        ]

    return [
        GraphNode("diagnose_template", "diagnose_template", "模板诊断", is_gate=False),
        GraphNode("draft_fields", "draft_fields", "AI 生成教案初稿", is_gate=False),
        GraphNode("pedagogy_review", "pedagogy_review", "教研质量审查", is_gate=False),
        GraphNode("revise_fields", "revise_fields", "根据审查修订", is_gate=False),
        GraphNode("teacher_review_gate", "teacher_review_gate",
                  "⏸ 等待老师确认修改", is_gate=True),
        GraphNode("export_docx", "export_docx", "按模板导出 Word", is_gate=False),
        GraphNode("evaluate_delivery", "evaluate_delivery", "交付检查", is_gate=False),
        GraphNode("generate_teacher_report", "generate_teacher_report",
                  "生成老师版报告", is_gate=False),
        GraphNode("save_history", "save_history", "保存历史", is_gate=False),
    ]
