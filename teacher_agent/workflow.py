from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

from .docx_filler import fill_docx_template
from .few_shot_examples import select_few_shot_examples
from .history_store import HistoryStore
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
    strict_ai: bool = False
    creative_mode: str = "常规稳妥"

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
            {"id": "anti_repetition", "label": "历史反重复", "layer": "质量层"},
            {"id": "lesson_writer", "label": "执教老师 Agent", "layer": "Agent 层"},
            {"id": "teaching_reviewer", "label": "教研组长 Agent", "layer": "Agent 层"},
            {"id": "lesson_reviser", "label": "二次修订 Agent", "layer": "Agent 层"},
            {"id": "doc_renderer", "label": "Word 渲染器", "layer": "工具层"},
            {"id": "history_store", "label": "历史记录", "layer": "数据层"},
        ],
        "edges": [
            ["app_input", "template_analyzer"],
            ["template_analyzer", "knowledge_context"],
            ["knowledge_context", "anti_repetition"],
            ["anti_repetition", "lesson_writer"],
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
    def __init__(self, history_db: Path | None = None) -> None:
        self._started_at = time.perf_counter()
        self.trace: list[WorkflowTraceEvent] = []
        self.history_db = history_db

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
        anti_repetition_context = self._build_anti_repetition_context(request)
        if anti_repetition_context:
            self._mark(
                "anti_repetition",
                "历史反重复",
                "done",
                "已读取近期相似教案，生成时会避开重复导入、活动顺序、作业和板书表达。",
            )
        else:
            self._mark("anti_repetition", "历史反重复", "done", "未发现近期相似教案，本次按新任务生成。")
        few_shot_examples = select_few_shot_examples(
            request.subject,
            request.grade,
            request.class_type,
            request.creative_mode,
        )
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
            request.strict_ai,
            request.creative_mode,
            anti_repetition_context,
            few_shot_examples,
        )
        self._mark("lesson_writer", "执教老师 Agent", "done", f"已生成 {len(field_map)} 个字段，来源：{generation_backend}。")

        context = {
            **request.to_dict(),
            "template_fields": template_analysis["mapped_fields"],
            "knowledge_summary": knowledge_context.source_summary,
            "anti_repetition_context": anti_repetition_context,
            "creative_mode": request.creative_mode,
            "strict_ai": request.strict_ai,
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
            "quality_controls": {
                "strict_ai": request.strict_ai,
                "creative_mode": request.creative_mode,
                "anti_repetition_used": bool(anti_repetition_context),
                "few_shot_used": bool(few_shot_examples),
            },
            "workflow_trace": [event.to_dict() for event in self.trace],
            "workflow_schema": build_workflow_schema(),
        }

    def _build_anti_repetition_context(self, request: LessonRequest) -> str:
        if not self.history_db:
            return ""
        try:
            documents = HistoryStore(self.history_db).find_similar_documents(
                subject=request.subject,
                grade=request.grade,
                title=request.title,
                limit=3,
            )
        except Exception:
            return ""
        if not documents:
            return ""
        chunks = []
        for index, item in enumerate(documents, start=1):
            chunks.append(
                "\n".join(
                    [
                        f"相似教案{index}：{item.get('grade','')}{item.get('subject','')}《{item.get('lesson_title','')}》",
                        f"课型/风格：{item.get('class_type','')} / {item.get('teaching_style','')}",
                        f"教学过程摘要：{item.get('teaching_process','')}",
                        f"作业摘要：{item.get('homework','')}",
                        f"板书摘要：{item.get('blackboard_design','')}",
                    ]
                )
            )
        return "\n\n".join(chunks)

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
