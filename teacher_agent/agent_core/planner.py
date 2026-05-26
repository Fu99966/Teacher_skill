from __future__ import annotations

from dataclasses import asdict, dataclass

from .task_router import AgentTask


@dataclass
class AgentPlanStep:
    id: str
    tool: str
    label: str
    status: str = "pending"
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def build_plan(task: AgentTask) -> list[AgentPlanStep]:
    if task.task_type != "lesson_plan":
        return [
            AgentPlanStep(
                id="unsupported_task",
                tool="none",
                label="暂不支持的任务",
                status="blocked",
                detail=f"当前 MVP 只支持 lesson_plan，识别到 {task.task_type}。",
            )
        ]

    return [
        AgentPlanStep("draft_lesson", "draft_lesson", "调用 V5 工作流生成并教研审阅"),
        AgentPlanStep("export_word", "export_word", "按学校模板导出 Word"),
        AgentPlanStep("evaluate_result", "evaluate_result", "检查字段、模板和 Word 结果"),
        AgentPlanStep("save_history", "save_history", "保存导出历史"),
        AgentPlanStep("save_memory", "save_memory", "记录本次 Agent 偏好"),
    ]
