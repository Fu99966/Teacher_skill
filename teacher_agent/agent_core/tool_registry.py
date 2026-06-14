from __future__ import annotations

from pathlib import Path
from typing import Any

from ..agent_observer import build_teacher_diagnostic_report
from ..history_store import HistoryStore
from ..template_parser import analyze_template
from ..template_profile import TemplateProfileStore
from ..workflow import TeacherWorkflow
from .evaluator import evaluate_delivery, evaluate_pedagogy_quality
from .memory import AgentMemoryStore, apply_exact_teacher_edit_memory, build_teacher_memory_context
from .pedagogy_reviser import revise_fields_from_pedagogy_review
from .state import AgentArtifact, AgentRunState
from .tool_spec import ToolRegistry, ToolSpec


def _st(context: dict[str, Any]) -> AgentRunState:
    return context["state"]


def build_agent_tool_registry(
    *,
    output_dir: Path,
    preview_dir: Path,
    history_db: Path,
    memory_db: Path,
) -> ToolRegistry:
    registry = ToolRegistry()

    def diagnose_template_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        template_path = Path(state.template_path or ".")
        analysis = analyze_template(template_path)

        profile_store = TemplateProfileStore(output_dir if output_dir else Path("outputs"))
        profile_id = profile_store.template_fingerprint(template_path)
        profile = profile_store.get_or_create(profile_id, analysis)
        analysis = profile_store.apply_profile(analysis, profile)

        state.template_analysis = analysis
        state.template_profile = profile
        state.status = "template_diagnosed"
        if profile.get("profile_hit") and (profile.get("last_successful_fill") or {}).get("filled_non_empty_count"):
            state.warnings.append("已加载该模板的历史成功画像。")
        state.artifacts.append(
            AgentArtifact(
                name="template_analysis",
                kind="json",
                summary=f"识别 {analysis.get('fillable_count', 0)} 个字段",
            )
        )
        return {
            "fillable_count": analysis.get("fillable_count"),
            "mapped_fields": analysis.get("mapped_fields"),
            "mode": analysis.get("mode"),
            "profile_hit": bool(profile.get("profile_hit")),
        }

    registry.register(
        "diagnose_template",
        diagnose_template_tool,
        ToolSpec(name="diagnose_template", description="解析 Word 模板并识别可填字段", retryable=True, critical=False),
    )

    def draft_fields_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        from ..lesson_generator import draft_lesson_document_fields_with_source, normalize_lesson_field_aliases

        task = state.task
        analysis = state.template_analysis or {}
        tmpl_fields = analysis.get("mapped_fields") or None
        material = str(task.get("material") or "")

        try:
            examples = AgentMemoryStore(memory_db).find_teacher_edit_examples(
                subject=str(task.get("subject") or ""),
                grade=str(task.get("grade") or ""),
                title=str(task.get("title") or ""),
                class_type=str(task.get("class_type") or ""),
                template_id=str(state.template_id or ""),
                limit=2,
            )
        except Exception:
            examples = []
        teacher_memory_context = build_teacher_memory_context(examples)

        fields, backend = draft_lesson_document_fields_with_source(
            subject=str(task.get("subject") or ""),
            grade=str(task.get("grade") or ""),
            title=str(task.get("title") or ""),
            material=material,
            class_hour=str(task.get("class_hour") or "1课时"),
            class_type=str(task.get("class_type") or "新授课"),
            teaching_style=str(task.get("teaching_style") or "常规启发式"),
            student_level=str(task.get("student_level") or "常规混合水平"),
            generation_depth=str(task.get("generation_depth") or "标准"),
            template_fields=tmpl_fields,
            strict_ai=bool(task.get("strict_ai", False)),
            template_context=analysis.get("field_context"),
            few_shot_examples=teacher_memory_context,
        )
        reused_fields: list[str] = []
        if backend == "local_fallback" and examples:
            fields, reused_fields = apply_exact_teacher_edit_memory(
                fields,
                examples,
                title=str(task.get("title") or ""),
                class_hour=str(task.get("class_hour") or ""),
                grade=str(task.get("grade") or ""),
                class_type=str(task.get("class_type") or ""),
                template_id=str(state.template_id or ""),
            )
            fields = normalize_lesson_field_aliases(fields, str(task.get("raw_text") or ""))
            if reused_fields:
                state.warnings.append("已复用同课题、同课时模板中的老师历史修改。")
        state.task["_generation_backend"] = backend
        state.task["_memory_fields_reused"] = reused_fields
        state.fields = fields
        state.status = "fields_generated"
        return {
            "generation_backend": backend,
            "field_count": len(fields),
            "memory_examples_used": len(examples),
            "memory_fields_reused": reused_fields,
        }

    registry.register(
        "draft_fields",
        draft_fields_tool,
        ToolSpec(name="draft_fields", description="生成教案字段内容", retryable=True, critical=True),
    )

    def pedagogy_review_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        report = evaluate_pedagogy_quality(state.fields or {}, state.task)
        state.review_report = report
        return {"score": report.get("score"), "passed": report.get("passed")}

    registry.register(
        "pedagogy_review",
        pedagogy_review_tool,
        ToolSpec(name="pedagogy_review", description="规则化教研质量检查", retryable=False, critical=False),
    )

    def revise_fields_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        review = dict(state.review_report or {})
        suggestions = review.get("suggestions") or []
        allowed_fields = list((state.template_analysis or {}).get("mapped_fields") or (state.fields or {}).keys())
        protected_fields = set((state.task or {}).get("_memory_fields_reused") or [])
        if str((state.task or {}).get("_generation_backend") or "").startswith("mock_"):
            protected_fields.update(allowed_fields)
        allowed_fields = [field for field in allowed_fields if field not in protected_fields]
        revised, changed_fields = revise_fields_from_pedagogy_review(
            state.fields or {},
            review,
            state.task or {},
            allowed_fields=allowed_fields,
        )
        state.fields = revised
        after_review = evaluate_pedagogy_quality(revised, state.task or {})
        after_review["revision"] = {
            "changed_fields": changed_fields,
            "before_score": review.get("score"),
            "after_score": after_review.get("score"),
            "after_passed": after_review.get("passed"),
            "initial_suggestions": suggestions,
        }
        state.review_report = after_review
        if changed_fields:
            state.warnings.append("教研修订已改进字段：" + "、".join(changed_fields))
        elif suggestions:
            state.warnings.append("教研检查建议已保留，未自动改写已合格字段。")
        return {
            "revised": bool(changed_fields),
            "suggestion_count": len(suggestions),
            "revised_fields": changed_fields,
            "after_score": after_review.get("score"),
        }

    registry.register(
        "revise_fields",
        revise_fields_tool,
        ToolSpec(name="revise_fields", description="根据审查结果标记修订建议", retryable=False, critical=False),
    )

    registry.register(
        "teacher_review_gate",
        lambda ctx: {"paused": True},
        ToolSpec(name="teacher_review_gate", description="暂停等待老师确认", retryable=False, critical=False),
    )

    def export_docx_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        template_analysis = state.template_analysis or {}
        required_fields = template_analysis.get("required_fields", [])
        missing_required = [
            field for field in required_fields
            if not str((state.fields or {}).get(field) or "").strip()
        ]
        if missing_required:
            state.status = "failed"
            message = "必填字段为空：" + "、".join(missing_required)
            state.errors.append(message)
            raise ValueError(message)

        workflow = TeacherWorkflow()
        export = workflow.export_document(
            state.fields or {},
            Path(state.template_path or "."),
            output_dir,
            preview_dir,
            repeat_fill_mode=str((state.task or {}).get("repeat_fill_mode") or "").strip() or None,
        )
        state.export_result = export
        state.artifacts.append(
            AgentArtifact(
                name="output_docx",
                url=export.get("download_url"),
                path=str(output_dir / str(export.get("output_name", ""))),
                kind="docx",
                summary="导出的 Word 教案",
            )
        )
        return {"output_name": export.get("output_name"), "download_url": export.get("download_url")}

    registry.register(
        "export_docx",
        export_docx_tool,
        ToolSpec(name="export_docx", description="按模板导出 Word 文档", retryable=True, critical=True),
    )

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

    registry.register(
        "evaluate_delivery",
        evaluate_delivery_tool,
        ToolSpec(name="evaluate_delivery", description="检查 Word 交付质量", retryable=True, critical=True),
    )

    def teacher_report_tool(context: dict[str, Any]) -> dict[str, Any]:
        state = _st(context)
        report = build_teacher_diagnostic_report(
            template_analysis=state.template_analysis,
            fill_report=(state.export_result or {}).get("fill_report", {}),
            evaluation_report=state.evaluation_report,
            fields=state.fields or {},
            template_profile=state.template_profile,
        )
        state.teacher_report = report.to_dict()
        state.teacher_report["markdown"] = report.to_markdown()

        fr = (state.export_result or {}).get("fill_report", {})
        if report.status == "passed" and fr.get("filled_non_empty_count", 0) > 0:
            try:
                profile_store = TemplateProfileStore(output_dir if output_dir else Path("outputs"))
                profile_id = profile_store.template_fingerprint(state.template_path or state.template_id or "unknown")
                profile_store.save_successful_mapping(
                    profile_id,
                    (state.template_analysis or {}).get("table_mappings", {}),
                    fr,
                    mapped_fields=(state.template_analysis or {}).get("mapped_fields", []),
                    repeat_fill_mode=fr.get("repeat_fill_mode"),
                    known_risks=report.reasons,
                )
            except Exception as exc:
                state.warnings.append(f"模板画像保存失败：{exc}")
        return {"report_generated": True, "status": report.status}

    registry.register(
        "generate_teacher_report",
        teacher_report_tool,
        ToolSpec(name="generate_teacher_report", description="生成老师可读的诊断报告", retryable=False, critical=False),
    )

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
                review_report=state.teacher_report,
                workflow_trace=state.trace,
            )
            AgentMemoryStore(memory_db).remember_agent_run(
                task=state.task,
                template_id=str(state.template_id or ""),
                output_name=str(export.get("output_name", "")),
                evaluation_passed=bool((state.evaluation_report or {}).get("passed")),
            )
            return {"saved": True}
        except Exception as exc:
            state.warnings.append(f"保存历史失败：{exc}")
            return {"saved": False}

    registry.register(
        "save_history",
        save_history_tool,
        ToolSpec(name="save_history", description="保存到历史记录", retryable=False, critical=False),
    )

    return registry


def build_lesson_tool_registry(
    *,
    output_dir: Path,
    preview_dir: Path,
    history_db: Path,
    memory_db: Path,
) -> ToolRegistry:
    return build_agent_tool_registry(
        output_dir=output_dir,
        preview_dir=preview_dir,
        history_db=history_db,
        memory_db=memory_db,
    )
