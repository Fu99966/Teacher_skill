from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .planner import AgentPlanStep
from .tool_registry import ToolRegistry


@dataclass
class AgentExecution:
    plan: list[AgentPlanStep]
    context: dict[str, Any]
    failed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "failed": self.failed,
            "plan": [step.to_dict() for step in self.plan],
        }


class AgentExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def run(self, plan: list[AgentPlanStep], context: dict[str, Any]) -> AgentExecution:
        failed = False
        for step in plan:
            if step.status == "blocked":
                failed = True
                continue
            try:
                step.status = "running"
                result = self.registry.get(step.tool)(context)
                step.status = "done"
                step.detail = _compact_detail(result)
            except Exception as exc:
                step.status = "error"
                step.detail = str(exc)
                failed = True
                break
        return AgentExecution(plan=plan, context=context, failed=failed)


def _compact_detail(result: dict[str, Any]) -> str:
    parts = []
    for key, value in result.items():
        if value is None:
            continue
        parts.append(f"{key}: {value}")
    return "；".join(parts) if parts else "完成"
