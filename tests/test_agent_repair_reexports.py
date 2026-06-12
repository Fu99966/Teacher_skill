from __future__ import annotations

from teacher_agent.agent_core.executor import AgentExecutor
from teacher_agent.agent_core.graph_planner import GraphNode
from teacher_agent.agent_core.state import AgentRunState
from teacher_agent.agent_core.tool_spec import ToolRegistry, ToolSpec


def test_agent_repair_reexports_before_second_delivery_check(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    export_calls: list[int] = []

    registry = ToolRegistry()

    def export_docx(context):
        state = context["state"]
        export_calls.append(len(export_calls) + 1)
        method_ready = bool(str((state.fields or {}).get("teaching_method") or "").strip())
        state.export_result = {
            "output_name": f"repair-{len(export_calls)}.docx",
            "download_url": f"/download/repair-{len(export_calls)}.docx",
            "fill_report": {
                "filled_non_empty_count": 3 if method_ready else 0,
                "field_write_counts": {
                    "lesson_title": 1 if method_ready else 0,
                    "teaching_process": 1 if method_ready else 0,
                    "teaching_method": 1 if method_ready else 0,
                },
                "errors": [] if method_ready else ["未写入任何非空字段"],
                "warnings": [],
            },
        }
        return {"output_name": state.export_result["output_name"]}

    def evaluate_delivery(context):
        state = context["state"]
        fill_report = (state.export_result or {}).get("fill_report", {})
        if int(fill_report.get("filled_non_empty_count") or 0) <= 0:
            state.evaluation_report = {"passed": False, "summary": "交付检查未通过"}
            raise ValueError("交付检查未通过")
        state.evaluation_report = {"passed": True, "summary": "交付检查通过"}
        return {"passed": True}

    registry.register(
        "export_docx",
        export_docx,
        ToolSpec(name="export_docx", description="export", retryable=False, critical=True),
    )
    registry.register(
        "evaluate_delivery",
        evaluate_delivery,
        ToolSpec(name="evaluate_delivery", description="evaluate", retryable=False, critical=True),
    )

    state = AgentRunState(
        session_id="repair-reexport",
        status="fields_generated",
        task={
            "subject": "物联网",
            "grade": "24级物联网班",
            "title": "PCB板设计",
            "class_hour": "32课时",
            "class_type": "项目实训课",
            "raw_text": "帮我生成一份 PCB板设计 32课时教案",
            "material": "",
        },
        current_node="",
        next_action="",
        template_analysis={"mapped_fields": ["lesson_title", "teaching_process", "teaching_method"]},
        fields={
            "lesson_title": "",
            "teaching_process": "帮我生成一份 PCB板设计 32课时教案",
            "teaching_method": "",
        },
        max_retries=1,
    )
    graph = [
        GraphNode("export_docx", "export_docx", "导出 Word"),
        GraphNode("evaluate_delivery", "evaluate_delivery", "交付检查"),
    ]

    result = AgentExecutor(registry).run(graph, state)

    assert result.status == "completed"
    assert export_calls == [1, 2]
    assert result.state.export_result["output_name"] == "repair-2.docx"
    assert result.state.export_result["fill_report"]["filled_non_empty_count"] > 0
    assert result.state.fields["teaching_method"].strip()
