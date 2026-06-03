from __future__ import annotations

from pathlib import Path
from typing import Any

from ..deepseek_client import DeepSeekError
from ..docx_grid import parse_table_grid
from ..history_store import HistoryStore
from ..lesson_generator import LessonGenerationError
from ..template_parser import analyze_template
from ..workflow import TeacherWorkflow
from .evaluator import evaluate_delivery, evaluate_pedagogy_quality
from .memory import AgentMemoryStore
from .state import AgentArtifact, AgentRunState
from .tool_spec import ToolRegistry, ToolSpec


def _st(context: dict[str, Any]) -> AgentRunState:
    """Extract AgentRunState from tool context."""
    return context["state"]


def build_agent_tool_registry(
    *,
    output_dir: Path,
    preview_dir: Path,
    history_db: Path,
    memory_db: Path,
) -> ToolRegistry:
    registry = ToolRegistry()

    # ── diagnose_template ──
    def diagnose_template_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        analysis = analyze_template(Path(state.template_path or "."))
        state.template_analysis = analysis

        # ── TemplateProfile integration ──
        from ...template_profile import TemplateProfileStore
        from pathlib import Path as _Path
        profile_store = TemplateProfileStore(_Path(output_dir) if output_dir else _Path("outputs"))
        profile = profile_store.get_or_create(
            state.template_id or "unknown", analysis
        )
        known = profile.get("last_successful_fill")
        if known and known.get("filled_non_empty_count", 0) > 0:
            state.warnings.append("已加载该模板的历史成功映射记录。")
        state.template_profile = profile

        state.status = "template_diagnosed"
        state.artifacts.append(AgentArtifact(
            name="template_analysis", kind="json",
            summary=f'识别 {analysis.get("fillable_count", 0)} 个字段',
        ))
        return {
            "fillable_count": analysis.get("fillable_count"),
            "mapped_fields": analysis.get("mapped_fields"),
            "mode": analysis.get("mode"),
        }

    registry.register("diagnose_template", diagnose_template_tool, ToolSpec(
        name="diagnose_template", description="解析Word模板识别可填字段",
        retryable=True, critical=False,
    ))

    # ── draft_fields ──
    def draft_fields_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        from ..lesson_generator import draft_lesson_document_fields_with_source
        task = state.task
        analysis = state.template_analysis or {}
        tmpl_fields = analysis.get("mapped_fields") or None
        fields, backend = draft_lesson_document_fields_with_source(
            task.get("subject", ""), task.get("grade", ""), task.get("title", ""),
            task.get("material", ""), task.get("class_hour", "1课时"),
            task.get("class_type", "新授课"), task.get("teaching_style", "常规启发式"),
            task.get("student_level", "常规混合水平"), task.get("generation_depth", "标准"),
            tmpl_fields, False, analysis.get("field_context"),
        )
        state.fields = fields
        state.status = "fields_generated"
        return {"generation_backend": backend, "field_count": len(fields)}

    registry.register("draft_fields", draft_fields_tool, ToolSpec(
        name="draft_fields", description="AI生成教案字段内容",
        retryable=True, critical=True,
    ))

    # ── pedagogy_review ──
    def pedagogy_review_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        report = evaluate_pedagogy_quality(state.fields or {}, state.task)
        state.review_report = report
        return {"score": report.get("score"), "passed": report.get("passed")}

    registry.register("pedagogy_review", pedagogy_review_tool, ToolSpec(
        name="pedagogy_review", description="教研质量审查（非LLM，规则检查）",
        retryable=False, critical=False,
    ))

    # ── revise_fields ──
    def revise_fields_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        review = state.review_report or {}
        suggestions = review.get("pedagogy_checks", [])
        if not suggestions:
            return {"revised": False, "reason": "无需修订"}
        # Mark that review was applied
        state.warnings.append(f"教研审查提出 {len(suggestions)} 条建议，已在第3步展示给老师查看。")
        return {"revised": True, "suggestion_count": len(suggestions)}

    registry.register("revise_fields", revise_fields_tool, ToolSpec(
        name="revise_fields", description="根据审查意见标记修订项",
        retryable=False, critical=False,
    ))

    # ── teacher_review_gate (no-op, executor handles it) ──
    registry.register("teacher_review_gate", lambda ctx: {"paused": True}, ToolSpec(
        name="teacher_review_gate", description="暂停等待老师确认",
        retryable=False, critical=False,
    ))

    # ── export_docx ──
    def export_docx_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        tp = Path(state.template_path or ".")

        # ── Validate required fields before export ──
        template_analysis = state.template_analysis or {}
        required_fields = template_analysis.get("required_fields", [])
        missing_required: list[str] = []
        for rf in required_fields:
            val = str(state.fields.get(rf, "")).strip() if state.fields else ""
            if not val:
                missing_required.append(rf)
        if missing_required:
            state.status = "failed"
            state.errors.append(
                f"required_field_empty: {', '.join(missing_required)} 为空，请补充后再导出。"
            )
            raise ValueError(
                f"必填字段为空: {', '.join(missing_required)}。请返回编辑页补充内容后再导出 Word。"
            )

        workflow = TeacherWorkflow()
        repeat_fill_mode = str((state.task or {}).get("repeat_fill_mode") or "").strip() or None
        export = workflow.export_document(
            state.fields or {},
            tp,
            output_dir,
            preview_dir,
            repeat_fill_mode=repeat_fill_mode,
        )
        state.export_result = export
        state.artifacts.append(AgentArtifact(
            name="output_docx",
            url=export.get("download_url"),
            path=str(output_dir / str(export.get("output_name", ""))),
            kind="docx", summary="导出的Word教案",
        ))
        return {
            "output_name": export.get("output_name"),
            "download_url": export.get("download_url"),
        }

    registry.register("export_docx", export_docx_tool, ToolSpec(
        name="export_docx", description="按模板导出Word文档",
        retryable=True, critical=True,
    ))

    # ── evaluate_delivery ──
    def evaluate_delivery_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        export = state.export_result or {}
        output_name = export.get("output_name")
        output_path = output_dir / output_name if output_name else None
        report = evaluate_delivery(
            fields=state.fields or {},
            output_path=output_path,
            download_url=export.get("download_url"),
            template_analysis=state.template_analysis,
            fill_report=export.get("fill_report"),
        )
        state.evaluation_report = report
        if not report.get("passed"):
            raise ValueError(report.get("summary", "交付检查失败"))
        return {"passed": report.get("passed"), "score": report.get("delivery_score", 0)}

    registry.register("evaluate_delivery", evaluate_delivery_tool, ToolSpec(
        name="evaluate_delivery", description="检查Word交付质量",
        retryable=True, critical=True,
    ))

    # ── generate_teacher_report ──
    def teacher_report_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        lines = []
        fl = {
            "lesson_title": "课题", "teaching_goals": "教学目的", "teaching_key_difficult": "重点难点",
            "teaching_process": "主要教学内容", "teaching_method": "教学方法的运用",
            "homework": "作业", "reflection": "课后小记",
        }
        lines.append("# 教案生成报告")
        lines.append("")
        er = state.evaluation_report or {}
        passed = er.get("passed", False)
        score = er.get("delivery_score", er.get("score", "?"))
        lines.append(f"## {'✅ 生成成功' if passed else '❌ 存在问题'}")
        lines.append(f"- 综合评分：{score}")
        lines.append(f"- 活动：{'; '.join(er.get('suggestions', [])[:3]) or '无建议'}")

        fwc = (state.export_result or {}).get("fill_report", {}).get("field_write_counts", {})
        if fwc:
            lines.append("- 各字段写入次数：")
            for f, c in sorted(fwc.items(), key=lambda x: -x[1]):
                lines.append(f"  - {fl.get(f, f)}：{c} 个位置")

        lines.append("")
        lines.append("## 建议")
        lines.append("请检查下载的 Word 教案中每个字段是否填写到正确位置。如发现问题，可重新上传模板生成。")
        state.teacher_report = {"summary": "\n".join(lines), "passed": passed}

        # ── Save successful mapping to TemplateProfile ──
        from ...template_profile import TemplateProfileStore
        from pathlib import Path as _Path
        fr = (state.export_result or {}).get("fill_report", {})
        if passed and fr.get("filled_non_empty_count", 0) > 0:
            try:
                profile_store = TemplateProfileStore(_Path(output_dir) if output_dir else _Path("outputs"))
                profile_store.save_successful_mapping(
                    state.template_id or "unknown",
                    (state.template_analysis or {}).get("table_mappings", {}),
                    fr,
                )
            except Exception:
                pass

        return {"report_generated": True}

    registry.register("generate_teacher_report", teacher_report_tool, ToolSpec(
        name="generate_teacher_report", description="生成老师可读的总结报告",
        retryable=False, critical=False,
    ))

    # ── save_history ──
    def save_history_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        export = state.export_result or {}
        try:
            HistoryStore(history_db).save_document(
                fields=state.fields or {},
                request_context=state.task,
                generation_backend="agent",
                template_mode=str((state.template_analysis or {}).get("mode", "unknown")),
                output_name=str(export.get("output_name", "")),
                download_url=str(export.get("download_url", "")),
                preview_url=export.get("preview_url"),
            )
            return {"saved": True}
        except Exception as e:
            state.warnings.append(f"保存历史失败：{e}")
            return {"saved": False}

    registry.register("save_history", save_history_tool, ToolSpec(
        name="save_history", description="保存到历史记录",
        retryable=False, critical=False,
    ))

    return registry


# ── Backward compat: old build_lesson_tool_registry ──

def build_lesson_tool_registry(
    *,
    output_dir: Path,
    preview_dir: Path,
    history_db: Path,
    memory_db: Path,
) -> ToolRegistry:
    """Old API kept for backward compatibility with existing web_app calls."""
    return build_agent_tool_registry(
        output_dir=output_dir, preview_dir=preview_dir,
        history_db=history_db, memory_db=memory_db,
    )
