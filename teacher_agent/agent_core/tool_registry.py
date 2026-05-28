from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..deepseek_client import DeepSeekError
from ..history_store import HistoryStore
from ..workflow import TeacherWorkflow
from .evaluator import evaluate_lesson_output
from .memory import AgentMemoryStore


ToolFn = Callable[[dict[str, Any]], dict[str, Any]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, func: ToolFn) -> None:
        self._tools[name] = func

    def get(self, name: str) -> ToolFn:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]


def build_lesson_tool_registry(
    *,
    output_dir: Path,
    preview_dir: Path,
    history_db: Path,
    memory_db: Path,
) -> ToolRegistry:
    registry = ToolRegistry()

    def draft_lesson(context: dict[str, Any]) -> dict[str, Any]:
        workflow = TeacherWorkflow(history_db=history_db)
        try:
            draft = workflow.draft(context["lesson_request"], context["template_path"], context["template_id"])
        except DeepSeekError as exc:
            context["llm_error"] = exc.to_dict()
            raise
        context["draft_result"] = draft
        context["fields"] = draft["fields"]
        context["workflow_trace"] = draft.get("workflow_trace", [])
        return {
            "generation_backend": draft.get("generation_backend"),
            "review_score": (draft.get("review_report") or {}).get("score"),
        }

    def export_word(context: dict[str, Any]) -> dict[str, Any]:
        workflow = TeacherWorkflow()
        export = workflow.export_document(context["fields"], context["template_path"], output_dir, preview_dir)
        context["export_result"] = export
        context["workflow_trace"] = context.get("workflow_trace", []) + export.get("workflow_trace", [])
        return {
            "output_name": export.get("output_name"),
            "download_url": export.get("download_url"),
            "preview_url": export.get("preview_url"),
        }

    def evaluate_result(context: dict[str, Any]) -> dict[str, Any]:
        export = context.get("export_result") or {}
        output_name = export.get("output_name")
        output_path = output_dir / output_name if output_name else None
        template_analysis = export.get("template_analysis") or (context.get("draft_result") or {}).get("template_analysis")
        report = evaluate_lesson_output(
            fields=context.get("fields") or {},
            output_path=output_path,
            download_url=export.get("download_url"),
            template_analysis=template_analysis,
        )
        context["evaluation_report"] = report.to_dict()
        return {"passed": report.passed, "summary": report.summary}

    def save_history(context: dict[str, Any]) -> dict[str, Any]:
        draft = context.get("draft_result") or {}
        export = context.get("export_result") or {}
        template_analysis = export.get("template_analysis") or draft.get("template_analysis") or {}
        history_item = HistoryStore(history_db).save_document(
            fields=context.get("fields") or {},
            request_context=context["lesson_request"].to_dict(),
            generation_backend=str(draft.get("generation_backend") or "agent"),
            template_mode=str(template_analysis.get("mode") or "unknown"),
            output_name=str(export.get("output_name") or ""),
            download_url=str(export.get("download_url") or ""),
            preview_url=export.get("preview_url"),
            review_report=draft.get("review_report"),
            workflow_trace=context.get("workflow_trace") or [],
        )
        context["history_item"] = history_item
        context["workflow_trace"].append(
            {
                "node": "history_store",
                "label": "历史记录",
                "status": "done",
                "detail": "Agent 已写入本地 SQLite 历史库。",
                "elapsed_ms": context["workflow_trace"][-1]["elapsed_ms"] if context.get("workflow_trace") else 0,
            }
        )
        return {"history_id": history_item["id"]}

    def save_memory(context: dict[str, Any]) -> dict[str, Any]:
        try:
            AgentMemoryStore(memory_db).remember_agent_run(
                task=context["agent_task"].to_dict(),
                template_id=context["template_id"],
                output_name=str((context.get("export_result") or {}).get("output_name") or ""),
                evaluation_passed=bool((context.get("evaluation_report") or {}).get("passed")),
            )
            return {"remembered": True}
        except Exception as exc:
            return {"remembered": False, "error": str(exc)}

    registry.register("draft_lesson", draft_lesson)
    registry.register("export_word", export_word)
    registry.register("evaluate_result", evaluate_result)
    registry.register("save_history", save_history)
    registry.register("save_memory", save_memory)
    return registry
