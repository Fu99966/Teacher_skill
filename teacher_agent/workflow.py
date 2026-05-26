from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

from .docx_filler import fill_docx_template
from .lesson_generator import coerce_lesson_fields, draft_lesson_document_fields_with_source, draft_lesson_fields_local
from .preview_renderer import render_docx_pdf_preview
from .rag_context import build_knowledge_context
from .teacher_agents import review_lesson_quality, revise_lesson_after_review
from .template_parser import analyze_template


@dataclass
class LessonRequest:
    subject: str
    grade: str
    title: str
    class_hour: str
    material: str
    class_type: str
    teaching_style: str
    student_level: str
    generation_depth: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class WorkflowTraceEvent:
    node: str
    label: str
    status: str
    detail: str
    elapsed_ms: int

    def to_dict(self) -> dict:
        return asdict(self)


def build_workflow_schema() -> dict:
    return {
        "version": "Teacher_skill V5",
        "name": "Dify-inspired Teacher Workflow",
        "nodes": [
            {"id": "app_input", "label": "应用输入", "layer": "应用层"},
            {"id": "template_analyzer", "label": "模板解析", "layer": "编排层"},
            {"id": "knowledge_context", "label": "RAG 上下文", "layer": "知识层"},
            {"id": "lesson_writer", "label": "执教老师 Agent", "layer": "Agent 层"},
            {"id": "teaching_reviewer", "label": "教研组长 Agent", "layer": "Agent 层"},
            {"id": "lesson_reviser", "label": "二次修订 Agent", "layer": "Agent 层"},
            {"id": "doc_renderer", "label": "Word 渲染器", "layer": "工具层"},
            {"id": "history_store", "label": "历史记录", "layer": "数据层"},
        ],
        "edges": [
            ["app_input", "template_analyzer"],
            ["template_analyzer", "knowledge_context"],
            ["knowledge_context", "lesson_writer"],
            ["lesson_writer", "teaching_reviewer"],
            ["teaching_reviewer", "lesson_reviser"],
            ["lesson_reviser", "doc_renderer"],
            ["doc_renderer", "history_store"],
        ],
    }


def _safe_filename(value: str, fallback: str = "lesson") -> str:
    import re

    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return value[:80] or fallback


class TeacherWorkflow:
    def __init__(self) -> None:
        self._started_at = time.perf_counter()
        self.trace: list[WorkflowTraceEvent] = []

    def _mark(self, node: str, label: str, status: str, detail: str) -> None:
        elapsed_ms = int((time.perf_counter() - self._started_at) * 1000)
        self.trace.append(WorkflowTraceEvent(node, label, status, detail, elapsed_ms))

    def draft(self, request: LessonRequest, template_path: Path, template_id: str) -> dict:
        self._mark("app_input", "应用输入", "done", "已接收课程信息、模板和教材内容。")

        template_analysis = analyze_template(template_path)
        mode = "占位符" if template_analysis["placeholders"] else "表格标签"
        self._mark(
            "template_analyzer",
            "模板解析",
            "done",
            f"已识别 {len(template_analysis['mapped_fields'])} 个字段，采用{mode}映射。",
        )

        knowledge_context = build_knowledge_context(
            request.material,
            subject=request.subject,
            title=request.title,
            class_type=request.class_type,
            teaching_style=request.teaching_style,
        )
        self._mark("knowledge_context", "RAG 上下文", "done", knowledge_context.source_summary)

        enhanced_material = knowledge_context.enhanced_material(request.material)
        template_fields = template_analysis["mapped_fields"] or None
        field_map, generation_backend = draft_lesson_document_fields_with_source(
            request.subject,
            request.grade,
            request.title,
            enhanced_material,
            request.class_hour,
            request.class_type,
            request.teaching_style,
            request.student_level,
            request.generation_depth,
            template_fields,
        )
        self._mark("lesson_writer", "执教老师 Agent", "done", f"已生成 {len(field_map)} 个字段，来源：{generation_backend}。")

        context = {
            **request.to_dict(),
            "template_fields": template_analysis["mapped_fields"],
            "knowledge_summary": knowledge_context.source_summary,
        }
        fallback_lesson = draft_lesson_fields_local(
            request.subject,
            request.grade,
            request.title,
            enhanced_material,
            request.class_hour,
            request.class_type,
            request.teaching_style,
            request.student_level,
            request.generation_depth,
        )
        fields = coerce_lesson_fields(field_map, fallback_lesson)
        review_report = review_lesson_quality(fields, context)
        self._mark(
            "teaching_reviewer",
            "教研组长 Agent",
            "done",
            f"预审完成，评分 {review_report.score}，来源：{review_report.backend}。",
        )

        fields, revision_backend = revise_lesson_after_review(fields, review_report, context)
        field_map.update(fields.to_dict())
        self._mark("lesson_reviser", "二次修订 Agent", "done", f"已根据审阅意见修订，来源：{revision_backend}。")

        return {
            "fields": field_map,
            "template_fields": template_analysis["mapped_fields"],
            "template_analysis": template_analysis,
            "template_id": template_id,
            "generation_backend": generation_backend,
            "revision_backend": revision_backend,
            "review_report": review_report.to_dict(),
            "knowledge_report": knowledge_context.to_dict(),
            "workflow_trace": [event.to_dict() for event in self.trace],
            "workflow_schema": build_workflow_schema(),
        }

    def export_document(
        self,
        fields: dict,
        template_path: Path,
        output_dir: Path,
        preview_dir: Path,
    ) -> dict:
        title = str(fields.get("lesson_title") or "教案")
        grade = str(fields.get("grade") or "年级")
        subject = str(fields.get("subject") or "学科")
        safe_title = _safe_filename(f"{grade}-{subject}-{title}-教案")
        output_name = f"{safe_title}-{time.strftime('%Y%m%d-%H%M%S')}.docx"
        output_path = output_dir / output_name

        fill_docx_template(template_path, fields, output_path)
        template_analysis = analyze_template(template_path)
        preview_pdf = render_docx_pdf_preview(output_path, preview_dir)
        preview_url = f"/preview/{quote(preview_pdf.name)}" if preview_pdf else None
        self._mark("doc_renderer", "Word 渲染器", "done", "已按原 Word 模板写入字段并生成下载文件。")

        return {
            "output_name": output_name,
            "download_url": f"/download/{quote(output_name)}",
            "preview_url": preview_url,
            "template_analysis": template_analysis,
            "workflow_trace": [event.to_dict() for event in self.trace],
        }
