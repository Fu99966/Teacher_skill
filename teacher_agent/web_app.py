from __future__ import annotations

import cgi
import json
import mimetypes
import re
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from .agent_core.executor import AgentExecutor
from .agent_core.evaluator import evaluate_lesson_output
from .agent_core.planner import build_plan
from .agent_core.task_router import route_task
from .agent_core.tool_registry import build_lesson_tool_registry
from .deepseek_client import DeepSeekError
from .history_store import HistoryStore
from .lesson_generator import (
    DEFAULT_CLASS_TYPE,
    DEFAULT_GENERATION_DEPTH,
    DEFAULT_STUDENT_LEVEL,
    DEFAULT_TEACHING_STYLE,
    LessonGenerationError,
    check_generation_health,
    refine_lesson_field,
)
from .sample_template import create_sample_template
from .template_parser import analyze_template
from .workflow import LessonRequest, TeacherWorkflow, build_workflow_schema


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
PREVIEW_DIR = OUTPUT_DIR / "previews"
HISTORY_DB = OUTPUT_DIR / "teacher_skill_history.sqlite3"
AGENT_MEMORY_DB = OUTPUT_DIR / "teacher_skill_agent_memory.sqlite3"
TEMPLATE_DIR = PROJECT_ROOT / "templates"
SAMPLE_MATERIAL = PROJECT_ROOT / "examples" / "sample_material.md"
SAMPLE_TEMPLATE = TEMPLATE_DIR / "sample_lesson_template.docx"


def _json_bytes(payload: dict, status: int = HTTPStatus.OK) -> tuple[int, bytes, str]:
    return status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"


def _safe_filename(value: str, fallback: str = "lesson") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return value[:80] or fallback


def _form_value(form: cgi.FieldStorage, name: str, default: str = "") -> str:
    item = form[name] if name in form else None
    if item is None or item.filename:
        return default
    value = item.value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _form_bool(form: cgi.FieldStorage, name: str, default: bool = False) -> bool:
    value = _form_value(form, name, "1" if default else "")
    return value.strip().lower() in {"1", "true", "yes", "on", "strict"}


def _template_id_for(path: Path) -> str:
    if path == SAMPLE_TEMPLATE:
        return "__sample__"
    return path.name


def _template_from_id(template_id: str) -> Path:
    if template_id == "__sample__":
        if not SAMPLE_TEMPLATE.exists():
            create_sample_template(SAMPLE_TEMPLATE)
        return SAMPLE_TEMPLATE

    path = (UPLOAD_DIR / Path(template_id).name).resolve()
    if UPLOAD_DIR.resolve() not in path.parents or not path.exists():
        raise ValueError("模板已失效，请重新上传模板")
    return path


def _template_mode_label(template_path: Path) -> str:
    return "system" if template_path == SAMPLE_TEMPLATE else "upload"


def _beginner_summary(evaluation_report: dict | None, is_generic_material: bool, template_mode: str) -> str:
    checks_ok = bool(evaluation_report and evaluation_report.get("passed"))
    quality_text = "已完成教研审阅和自动检查" if checks_ok else "已完成教案生成，建议下载前再快速预览"
    template_text = "系统标准模板" if template_mode == "system" else "学校上传模板"
    material_text = "本次未填写教材内容，已生成通用版。" if is_generic_material else "已结合教材内容生成。"
    return f"{quality_text}，并写入{template_text}。{material_text}"


class TeacherAgentHandler(BaseHTTPRequestHandler):
    server_version = "TeacherAgentWeb/0.1"

    def log_message(self, format: str, *args) -> None:
        print("[%s] %s" % (self.log_date_time_string(), format % args))

    def _send(
        self,
        status: int,
        body: bytes,
        content_type: str,
        filename: str | None = None,
        include_body: bool = True,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        if filename:
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filename)}")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def _send_file(self, path: Path, as_attachment: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self._send(*_json_bytes({"error": "文件不存在"}, HTTPStatus.NOT_FOUND))
            return

        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        filename = path.name if as_attachment else None
        self._send(HTTPStatus.OK, path.read_bytes(), content_type, filename)

    def _send_file_headers(self, path: Path, as_attachment: bool = False) -> None:
        if not path.exists() or not path.is_file():
            self._send(*_json_bytes({"error": "文件不存在"}, HTTPStatus.NOT_FOUND), include_body=False)
            return

        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        filename = path.name if as_attachment else None
        self._send(HTTPStatus.OK, path.read_bytes(), content_type, filename, include_body=False)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in {"/", "/index.html"}:
            self._send_file(WEB_ROOT / "index.html")
            return

        if path.startswith("/static/"):
            static_path = (WEB_ROOT / path.removeprefix("/")).resolve()
            if WEB_ROOT.resolve() not in static_path.parents:
                self._send(*_json_bytes({"error": "非法路径"}, HTTPStatus.BAD_REQUEST))
                return
            self._send_file(static_path)
            return

        if path == "/api/sample-material":
            material = SAMPLE_MATERIAL.read_text(encoding="utf-8") if SAMPLE_MATERIAL.exists() else ""
            self._send(*_json_bytes({"material": material}))
            return

        if path == "/api/workflow-schema":
            self._send(*_json_bytes(build_workflow_schema()))
            return

        if path == "/api/history":
            history = HistoryStore(HISTORY_DB).list_documents()
            self._send(*_json_bytes({"items": history}))
            return

        if path == "/api/llm-health":
            probe = "probe=1" in (parsed.query or "")
            self._send(*_json_bytes({"llm": check_generation_health(probe=probe).to_dict()}))
            return

        if path == "/download/sample-template":
            if not SAMPLE_TEMPLATE.exists():
                create_sample_template(SAMPLE_TEMPLATE)
            self._send_file(SAMPLE_TEMPLATE, as_attachment=True)
            return

        if path.startswith("/download/"):
            name = Path(path.removeprefix("/download/")).name
            self._send_file(OUTPUT_DIR / name, as_attachment=True)
            return

        if path.startswith("/preview/"):
            name = Path(path.removeprefix("/preview/")).name
            self._send_file(PREVIEW_DIR / name, as_attachment=False)
            return

        if path == "/health":
            self._send(*_json_bytes({"ok": True}))
            return

        self._send(*_json_bytes({"error": "页面不存在"}, HTTPStatus.NOT_FOUND))

    def do_HEAD(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in {"/", "/index.html"}:
            self._send_file_headers(WEB_ROOT / "index.html")
            return

        if path == "/download/sample-template":
            if not SAMPLE_TEMPLATE.exists():
                create_sample_template(SAMPLE_TEMPLATE)
            self._send_file_headers(SAMPLE_TEMPLATE, as_attachment=True)
            return

        if path.startswith("/download/"):
            name = Path(path.removeprefix("/download/")).name
            self._send_file_headers(OUTPUT_DIR / name, as_attachment=True)
            return

        if path.startswith("/preview/"):
            name = Path(path.removeprefix("/preview/")).name
            self._send_file_headers(PREVIEW_DIR / name, as_attachment=False)
            return

        self._send(*_json_bytes({"ok": True}), include_body=False)

    def do_OPTIONS(self) -> None:
        self._send(HTTPStatus.NO_CONTENT, b"", "text/plain; charset=utf-8", include_body=False)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/draft":
            try:
                self._handle_draft()
            except DeepSeekError as exc:
                self._send(*_json_bytes({"error": exc.user_message, "llm_error": exc.to_dict()}, HTTPStatus.BAD_GATEWAY))
            except LessonGenerationError as exc:
                self._send(
                    *_json_bytes(
                        {"error": str(exc), "llm_error": {"message": str(exc), "type": "generation_error"}},
                        HTTPStatus.BAD_GATEWAY,
                    )
                )
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        if parsed.path == "/api/export":
            try:
                self._handle_export()
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        if parsed.path == "/api/refine-field":
            try:
                self._handle_refine_field()
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        if parsed.path == "/api/agent-preview":
            try:
                self._handle_agent_preview()
            except ValueError as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.BAD_REQUEST))
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        if parsed.path == "/api/agent-run":
            try:
                self._handle_agent_run()
            except ValueError as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.BAD_REQUEST))
            except DeepSeekError as exc:
                self._send(*_json_bytes({"error": exc.user_message, "llm_error": exc.to_dict()}, HTTPStatus.BAD_GATEWAY))
            except LessonGenerationError as exc:
                self._send(
                    *_json_bytes(
                        {"error": str(exc), "llm_error": {"message": str(exc), "type": "generation_error"}},
                        HTTPStatus.BAD_GATEWAY,
                    )
                )
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        if parsed.path == "/api/step1-diagnose":
            try:
                self._handle_step1_diagnose()
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        if parsed.path == "/api/step2-generate":
            try:
                self._handle_step2_generate()
            except DeepSeekError as exc:
                self._send(*_json_bytes({"error": exc.user_message, "llm_error": exc.to_dict()}, HTTPStatus.BAD_GATEWAY))
            except LessonGenerationError as exc:
                self._send(*_json_bytes({"error": str(exc), "llm_error": {"message": str(exc), "type": "generation_error"}}, HTTPStatus.BAD_GATEWAY))
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        if parsed.path == "/api/step4-fill":
            try:
                self._handle_step4_fill()
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        # ── Agent API routes ──
        agent_start_match = re.match(r"^/api/agent/start$", parsed.path)
        if agent_start_match:
            try:
                self._handle_agent_start()
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        agent_get_match = re.match(r"^/api/agent/([^/]+)$", parsed.path)
        if agent_get_match and self.command == "GET":
            try:
                self._handle_agent_get(agent_get_match.group(1))
            except KeyError:
                self._send(*_json_bytes({"error": "Session not found"}, HTTPStatus.NOT_FOUND))
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        agent_continue_match = re.match(r"^/api/agent/([^/]+)/continue$", parsed.path)
        if agent_continue_match:
            try:
                self._handle_agent_continue(agent_continue_match.group(1))
            except KeyError:
                self._send(*_json_bytes({"error": "Session not found"}, HTTPStatus.NOT_FOUND))
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        agent_cancel_match = re.match(r"^/api/agent/([^/]+)/cancel$", parsed.path)
        if agent_cancel_match:
            try:
                self._handle_agent_cancel(agent_cancel_match.group(1))
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        agent_repair_match = re.match(r"^/api/agent/([^/]+)/repair$", parsed.path)
        if agent_repair_match:
            try:
                self._handle_agent_repair(agent_repair_match.group(1))
            except Exception as exc:
                self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))
            return

        if parsed.path != "/api/generate":
            self._send(*_json_bytes({"error": "接口不存在"}, HTTPStatus.NOT_FOUND))
            return

        try:
            self._handle_generate()
        except DeepSeekError as exc:
            self._send(*_json_bytes({"error": exc.user_message, "llm_error": exc.to_dict()}, HTTPStatus.BAD_GATEWAY))
        except LessonGenerationError as exc:
            self._send(
                *_json_bytes(
                    {"error": str(exc), "llm_error": {"message": str(exc), "type": "generation_error"}},
                    HTTPStatus.BAD_GATEWAY,
                )
            )
        except Exception as exc:
            self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))

    def _handle_step1_diagnose(self) -> None:
        """Step 1: upload template, return template analysis."""
        form = self._read_multipart_form()
        template_path = self._save_template(form)
        analysis = analyze_template(template_path)
        self._send(*_json_bytes({"analysis": analysis, "template_path": str(template_path)}))

    def _handle_step2_generate(self) -> None:
        """Step 2: generate lesson fields from course info + template."""
        from .lesson_generator import draft_lesson_document_fields_with_source
        form = self._read_multipart_form()
        template_path = self._save_template(form)
        subject = _form_value(form, "subject", "")
        grade = _form_value(form, "grade", "")
        title = _form_value(form, "title", "")
        class_hour = _form_value(form, "class_hour", "1课时")
        material = _form_value(form, "material", "")
        class_type = _form_value(form, "class_type", DEFAULT_CLASS_TYPE)
        teaching_style = _form_value(form, "teaching_style", DEFAULT_TEACHING_STYLE)
        strict_ai = _form_bool(form, "strict_ai", False)
        template_analysis = analyze_template(template_path)
        template_fields = template_analysis.get("mapped_fields") or None
        fields, backend = draft_lesson_document_fields_with_source(
            subject, grade, title, material, class_hour,
            class_type, teaching_style, DEFAULT_STUDENT_LEVEL, DEFAULT_GENERATION_DEPTH,
            template_fields, strict_ai, template_analysis.get("field_context"),
        )
        self._send(*_json_bytes({
            "fields": fields,
            "generation_backend": backend,
            "template_analysis": template_analysis,
            "template_fields": template_fields,
            "template_id": _template_id_for(template_path),
        }))

    def _handle_step4_fill(self) -> None:
        """Step 4: fill template with provided fields JSON and return download URL."""
        import json as _json
        from .docx_filler import fill_docx_template
        form = self._read_multipart_form()
        template_path = self._save_template(form)
        fields_json = _form_value(form, "fields_json", "{}")
        fields = _json.loads(fields_json)
        if not isinstance(fields, dict) or not fields:
            raise ValueError("fields_json 格式错误或为空")
        template_analysis = analyze_template(template_path)
        grade = str(fields.get("grade") or fields.get("class_name") or "年级")
        subject = str(fields.get("subject") or "学科")
        title = str(fields.get("lesson_title") or "教案")
        safe_title = _safe_filename(f"{grade}-{subject}-{title}-教案")
        output_name = f"{safe_title}-{time.strftime('%Y%m%d-%H%M%S')}.docx"
        output_path = OUTPUT_DIR / output_name
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        fill_report = fill_docx_template(template_path, fields, output_path)
        self._send(*_json_bytes({
            "fill_report": fill_report.to_dict(),
            "download_url": f"/download/{quote(output_name)}",
            "output_name": output_name,
            "template_analysis": template_analysis,
        }))

    def _handle_agent_start(self) -> None:
        """POST /api/agent/start – Start agent, pause at teacher_review_gate."""
        import uuid
        from .agent_core.checkpoint import AgentCheckpointStore
        from .agent_core.graph_planner import build_graph
        from .agent_core.state import AgentRunState
        from .agent_core.tool_registry import build_agent_tool_registry
        from .agent_core.executor import AgentExecutor
        from .agent_core.task_router import route_task

        form = self._read_multipart_form()
        template_path = self._save_template(form)
        template_id = _template_id_for(template_path)
        analysis = analyze_template(template_path)

        agent_request = _form_value(form, "agent_request", "")
        subject = _form_value(form, "subject", "物联网")
        grade = _form_value(form, "grade", "24物联网1班")
        title = _form_value(form, "title", "未命名课题")
        material = _form_value(form, "material", "")
        class_hour = _form_value(form, "class_hour", "1课时")
        class_type = _form_value(form, "class_type", DEFAULT_CLASS_TYPE)
        teaching_style = _form_value(form, "teaching_style", DEFAULT_TEACHING_STYLE)

        task = route_task(agent_request or f"生成{subject}{grade}{title}教案", {
            "subject": subject, "grade": grade, "title": title,
            "class_hour": class_hour, "class_type": class_type, "teaching_style": teaching_style,
        })
        session_id = uuid.uuid4().hex[:12]
        task_dict = task.to_dict()
        task_dict["material"] = material

        state = AgentRunState(
            session_id=session_id, status="initialized", task=task_dict,
            current_node="", next_action="", template_path=str(template_path),
            template_id=template_id, template_analysis=analysis,
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        registry = build_agent_tool_registry(
            output_dir=OUTPUT_DIR, preview_dir=PREVIEW_DIR,
            history_db=HISTORY_DB, memory_db=AGENT_MEMORY_DB,
        )
        checkpoint = AgentCheckpointStore(OUTPUT_DIR)
        executor = AgentExecutor(registry, checkpoint)

        graph = build_graph(task)
        result = executor.run(graph, state)

        self._send(*_json_bytes(result.to_dict()))

    def _handle_agent_get(self, session_id: str) -> None:
        """GET /api/agent/{session_id} – Get current agent state."""
        from .agent_core.checkpoint import AgentCheckpointStore
        checkpoint = AgentCheckpointStore(OUTPUT_DIR)
        state = checkpoint.load(session_id)
        if state is None:
            raise KeyError(session_id)
        self._send(*_json_bytes(state.to_dict()))

    def _handle_agent_continue(self, session_id: str) -> None:
        """POST /api/agent/{session_id}/continue – Continue after teacher review."""
        import json as _json
        from .agent_core.checkpoint import AgentCheckpointStore
        from .agent_core.graph_planner import build_graph
        from .agent_core.state import AgentRunState
        from .agent_core.tool_registry import build_agent_tool_registry
        from .agent_core.executor import AgentExecutor
        from .agent_core.task_router import AgentTask

        checkpoint = AgentCheckpointStore(OUTPUT_DIR)
        state = checkpoint.load(session_id)
        if state is None:
            raise KeyError(session_id)

        content_type = self.headers.get("Content-Type", "")
        teacher_edits: dict[str, Any] = {}
        if "application/json" in content_type:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(content_length).decode("utf-8")
            teacher_edits = _json.loads(body).get("teacher_edits", {})
        elif "multipart/form-data" in content_type:
            form = self._read_multipart_form()
            edits_json = _form_value(form, "teacher_edits", "{}")
            teacher_edits = _json.loads(edits_json)

        if teacher_edits:
            fields = state.fields or {}
            fields.update(teacher_edits)
            state.fields = fields
            state.teacher_edits = teacher_edits
            state.status = "fields_generated"

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        registry = build_agent_tool_registry(
            output_dir=OUTPUT_DIR, preview_dir=PREVIEW_DIR,
            history_db=HISTORY_DB, memory_db=AGENT_MEMORY_DB,
        )
        executor = AgentExecutor(registry, checkpoint)
        # Rebuild graph for task
        task = AgentTask(
            raw_request=str(state.task.get("raw_request", "")),
            task_type="lesson_plan", subject=str(state.task.get("subject", "")),
            grade=str(state.task.get("grade", "")), title=str(state.task.get("title", "")),
            class_hour=str(state.task.get("class_hour", "1课时")),
            class_type=str(state.task.get("class_type", "新授课")),
            teaching_style=str(state.task.get("teaching_style", "常规启发式")),
            student_level=str(state.task.get("student_level", "常规混合水平")),
            generation_depth=str(state.task.get("generation_depth", "标准")),
            missing_fields=[], confidence=0.9, notes=[],
        )
        group = build_graph(task)
        result = executor.continue_from_gate(group, state)
        self._send(*_json_bytes(result.to_dict()))

    def _handle_agent_cancel(self, session_id: str) -> None:
        """POST /api/agent/{session_id}/cancel"""
        from .agent_core.checkpoint import AgentCheckpointStore
        checkpoint = AgentCheckpointStore(OUTPUT_DIR)
        checkpoint.delete(session_id)
        self._send(*_json_bytes({"cancelled": True}))

    def _handle_agent_repair(self, session_id: str) -> None:
        """POST /api/agent/{session_id}/repair – Attempt repair."""
        from .agent_core.checkpoint import AgentCheckpointStore
        from .agent_core.repair import repair_state

        checkpoint = AgentCheckpointStore(OUTPUT_DIR)
        state = checkpoint.load(session_id)
        if state is None:
            raise KeyError(session_id)

        state = repair_state(state)
        checkpoint.save(state)
        self._send(*_json_bytes(state.to_dict()))

    def _read_multipart_form(self) -> cgi.FieldStorage:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ValueError("请使用表单提交")

        return cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
            encoding="utf-8",
            errors="replace",
        )

    def _read_lesson_form(self) -> tuple[cgi.FieldStorage, str, str, str, str, str, str, str, str, str, bool, str, Path, dict]:
        form = self._read_multipart_form()

        subject = _form_value(form, "subject", "语文")
        grade = _form_value(form, "grade", "四年级")
        title = _form_value(form, "title", "未命名课题")
        class_hour = _form_value(form, "class_hour", "1课时")
        material = _form_value(form, "material", "")
        class_type = _form_value(form, "class_type", DEFAULT_CLASS_TYPE)
        teaching_style = _form_value(form, "teaching_style", DEFAULT_TEACHING_STYLE)
        student_level = _form_value(form, "student_level", DEFAULT_STUDENT_LEVEL)
        generation_depth = _form_value(form, "generation_depth", DEFAULT_GENERATION_DEPTH)
        strict_ai = _form_bool(form, "strict_ai", False)
        creative_mode = _form_value(form, "creative_mode", "常规稳妥")

        template_path = self._save_template(form)
        template_analysis = analyze_template(template_path)
        return (
            form,
            subject,
            grade,
            title,
            class_hour,
            material,
            class_type,
            teaching_style,
            student_level,
            generation_depth,
            strict_ai,
            creative_mode,
            template_path,
            template_analysis,
        )

    def _read_agent_form(self) -> tuple[
        cgi.FieldStorage,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        str,
        Path,
        dict,
        bool,
        str,
        str,
        bool,
    ]:
        form = self._read_multipart_form()

        subject = _form_value(form, "subject", "")
        grade = _form_value(form, "grade", "")
        title = _form_value(form, "title", "")
        class_hour = _form_value(form, "class_hour", "1课时")
        material = _form_value(form, "material", "")
        class_type = _form_value(form, "class_type", DEFAULT_CLASS_TYPE)
        teaching_style = _form_value(form, "teaching_style", DEFAULT_TEACHING_STYLE)
        student_level = _form_value(form, "student_level", DEFAULT_STUDENT_LEVEL)
        generation_depth = _form_value(form, "generation_depth", DEFAULT_GENERATION_DEPTH)
        strict_ai = _form_bool(form, "strict_ai", True)
        creative_mode = _form_value(form, "creative_mode", "更像公开课")
        template_mode = _form_value(form, "template_mode", "upload").strip() or "upload"
        if template_mode not in {"system", "upload"}:
            raise ValueError("模板模式无效，请选择系统模板或上传模板")
        if template_mode == "upload":
            template_item = form["template"] if "template" in form else None
            if template_item is None or not template_item.filename:
                raise ValueError("请上传学校 Word 模板，或选择使用系统标准模板")

        template_path = self._save_template(form, allow_sample=template_mode == "system")
        template_analysis = analyze_template(template_path)
        return (
            form,
            subject,
            grade,
            title,
            class_hour,
            material,
            class_type,
            teaching_style,
            student_level,
            generation_depth,
            template_path,
            template_analysis,
            strict_ai,
            creative_mode,
            _template_mode_label(template_path),
            not material.strip(),
        )

    def _handle_draft(self) -> None:
        (
            _,
            subject,
            grade,
            title,
            class_hour,
            material,
            class_type,
            teaching_style,
            student_level,
            generation_depth,
            strict_ai,
            creative_mode,
            template_path,
            template_analysis,
        ) = self._read_lesson_form()
        request = LessonRequest(
            subject,
            grade,
            title,
            class_hour,
            material,
            class_type,
            teaching_style,
            student_level,
            generation_depth,
            strict_ai,
            creative_mode,
        )
        workflow = TeacherWorkflow(history_db=HISTORY_DB)
        result = workflow.draft(request, template_path, _template_id_for(template_path), template_analysis)

        # Keep this local variable referenced so template analysis failures are
        # surfaced before generation starts.
        result["template_analysis"] = result.get("template_analysis") or template_analysis
        result["llm_status"] = check_generation_health(probe=False).to_dict()
        self._send(*_json_bytes(result))

    def _handle_refine_field(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        payload = json.loads(self.rfile.read(content_length).decode("utf-8"))

        field = str(payload.get("field") or "")
        value = str(payload.get("value") or "")
        action = str(payload.get("action") or "more_vivid")
        instruction = str(payload.get("instruction") or "")
        if not field:
            raise ValueError("缺少字段名")

        refined = refine_lesson_field(field, value, action, instruction)
        self._send(*_json_bytes({"field": field, "value": refined}))

    def _read_agent_preview_payload(self) -> dict:
        content_type = self.headers.get("Content-Type", "")
        if "application/json" in content_type:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(content_length).decode("utf-8")
            return json.loads(body or "{}")

        if "multipart/form-data" in content_type:
            form = self._read_multipart_form()
            return {
                "agent_request": _form_value(form, "agent_request", ""),
                "subject": _form_value(form, "subject", ""),
                "grade": _form_value(form, "grade", ""),
                "title": _form_value(form, "title", ""),
                "class_hour": _form_value(form, "class_hour", ""),
                "class_type": _form_value(form, "class_type", ""),
                "teaching_style": _form_value(form, "teaching_style", ""),
                "student_level": _form_value(form, "student_level", ""),
                "generation_depth": _form_value(form, "generation_depth", ""),
            }

        if "application/x-www-form-urlencoded" in content_type:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            values = parse_qs(self.rfile.read(content_length).decode("utf-8"), keep_blank_values=True)
            return {key: items[0] if items else "" for key, items in values.items()}

        raise ValueError("请使用 JSON 或表单提交")

    def _handle_agent_preview(self) -> None:
        payload = self._read_agent_preview_payload()
        agent_request = str(payload.get("agent_request") or "")
        if not agent_request.strip():
            raise ValueError("请先输入备课需求")

        defaults = {
            "subject": str(payload.get("subject") or ""),
            "grade": str(payload.get("grade") or ""),
            "title": str(payload.get("title") or ""),
            "class_hour": str(payload.get("class_hour") or ""),
            "class_type": str(payload.get("class_type") or ""),
            "teaching_style": str(payload.get("teaching_style") or ""),
            "student_level": str(payload.get("student_level") or ""),
            "generation_depth": str(payload.get("generation_depth") or ""),
        }
        task = route_task(agent_request, defaults)
        plan = build_plan(task)
        self._send(
            *_json_bytes(
                {
                    "agent_task": task.to_dict(),
                    "agent_plan": [step.to_dict() for step in plan],
                    "needs_input": bool(task.missing_fields),
                    "missing_fields": task.missing_fields,
                }
            )
        )

    def _handle_agent_run(self) -> None:
        (
            form,
            subject,
            grade,
            title,
            class_hour,
            material,
            class_type,
            teaching_style,
            student_level,
            generation_depth,
            template_path,
            template_analysis,
            strict_ai,
            creative_mode,
            actual_template_mode,
            is_generic_material,
        ) = self._read_agent_form()
        agent_request = _form_value(form, "agent_request", "")
        if not agent_request.strip():
            raise ValueError("请先输入 Agent 指令")

        defaults = {
            "subject": subject,
            "grade": grade,
            "title": title,
            "class_hour": class_hour,
            "class_type": class_type if class_type != DEFAULT_CLASS_TYPE else "",
            "teaching_style": teaching_style if teaching_style != DEFAULT_TEACHING_STYLE else "",
            "student_level": student_level if student_level != DEFAULT_STUDENT_LEVEL else "",
            "generation_depth": generation_depth if generation_depth != DEFAULT_GENERATION_DEPTH else "",
        }
        task = route_task(agent_request, defaults)
        plan = build_plan(task)

        if task.missing_fields:
            self._send(
                *_json_bytes(
                    {
                        "needs_input": True,
                        "agent_task": task.to_dict(),
                        "agent_plan": [step.to_dict() for step in plan],
                        "missing_fields": task.missing_fields,
                        "message": "Agent 需要补齐学科、年级或课题后再执行。",
                    },
                    HTTPStatus.BAD_REQUEST,
                )
            )
            return

        if task.task_type != "lesson_plan":
            self._send(
                *_json_bytes(
                    {
                        "needs_input": True,
                        "agent_task": task.to_dict(),
                        "agent_plan": [step.to_dict() for step in plan],
                        "message": "当前 Agent MVP 只支持教案生成任务。",
                    },
                    HTTPStatus.BAD_REQUEST,
                )
            )
            return

        lesson_request = LessonRequest(
            task.subject,
            task.grade,
            task.title,
            task.class_hour,
            material or agent_request,
            task.class_type,
            task.teaching_style,
            task.student_level,
            task.generation_depth,
            strict_ai,
            creative_mode,
        )
        context = {
            "agent_task": task,
            "lesson_request": lesson_request,
            "template_path": template_path,
            "template_id": _template_id_for(template_path),
            "template_analysis": template_analysis,
        }
        registry = build_lesson_tool_registry(
            output_dir=OUTPUT_DIR,
            preview_dir=PREVIEW_DIR,
            history_db=HISTORY_DB,
            memory_db=AGENT_MEMORY_DB,
        )
        execution = AgentExecutor(registry).run(plan, context)
        draft_result = context.get("draft_result") or {}
        export_result = context.get("export_result") or {}

        payload = {
            **draft_result,
            "error": (context.get("llm_error") or {}).get("message") if context.get("llm_error") else None,
            "llm_error": context.get("llm_error"),
            "fields": context.get("fields") or draft_result.get("fields") or {},
            "template_fields": template_analysis["mapped_fields"],
            "template_analysis": export_result.get("template_analysis") or draft_result.get("template_analysis") or template_analysis,
            "template_id": _template_id_for(template_path),
            "agent_task": task.to_dict(),
            "agent_plan": [step.to_dict() for step in execution.plan],
            "agent_failed": execution.failed,
            "evaluation_report": context.get("evaluation_report"),
            "output_name": export_result.get("output_name"),
            "download_url": export_result.get("download_url"),
            "preview_url": export_result.get("preview_url"),
            "fill_report": export_result.get("fill_report"),
            "workflow_trace": context.get("workflow_trace") or draft_result.get("workflow_trace") or [],
            "history_item": context.get("history_item"),
            "template_mode": actual_template_mode,
            "is_generic_material": is_generic_material,
            "llm_status": check_generation_health(probe=False).to_dict(),
            "quality_controls": draft_result.get("quality_controls") or {},
            "beginner_summary": _beginner_summary(
                evaluation_report=context.get("evaluation_report"),
                is_generic_material=is_generic_material,
                template_mode=actual_template_mode,
            ),
        }
        if context.get("llm_error"):
            self._send(*_json_bytes(payload, HTTPStatus.BAD_GATEWAY))
            return
        self._send(*_json_bytes(payload, HTTPStatus.INTERNAL_SERVER_ERROR if execution.failed else HTTPStatus.OK))

    def _handle_export(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0") or "0")
        payload = json.loads(self.rfile.read(content_length).decode("utf-8"))

        fields = payload.get("fields")
        template_id = payload.get("template_id")
        if not isinstance(fields, dict):
            raise ValueError("缺少教案字段")
        if not isinstance(template_id, str):
            raise ValueError("缺少模板信息")

        template_path = _template_from_id(template_id)
        workflow = TeacherWorkflow()
        result = workflow.export_document(fields, template_path, OUTPUT_DIR, PREVIEW_DIR)
        output_path = OUTPUT_DIR / str(result.get("output_name") or "")
        evaluation = evaluate_lesson_output(
            fields=fields,
            output_path=output_path,
            download_url=result.get("download_url"),
            template_analysis=result.get("template_analysis"),
            fill_report=result.get("fill_report"),
        )
        result["evaluation_report"] = evaluation.to_dict()

        prior_trace = payload.get("workflow_trace")
        if isinstance(prior_trace, list):
            result["workflow_trace"] = prior_trace + result["workflow_trace"]

        request_context = payload.get("request_context") if isinstance(payload.get("request_context"), dict) else {}
        review_report = payload.get("review_report") if isinstance(payload.get("review_report"), dict) else {}
        generation_backend = str(payload.get("generation_backend") or "manual_export")
        template_mode = result["template_analysis"].get("mode", "unknown")
        result["workflow_trace"].append(
            {
                "node": "history_store",
                "label": "历史记录",
                "status": "done",
                "detail": "已写入本地 SQLite 历史库，便于教师找回最近导出。",
                "elapsed_ms": result["workflow_trace"][-1]["elapsed_ms"] if result["workflow_trace"] else 0,
            }
        )
        history_item = HistoryStore(HISTORY_DB).save_document(
            fields=fields,
            request_context=request_context,
            generation_backend=generation_backend,
            template_mode=template_mode,
            output_name=result["output_name"],
            download_url=result["download_url"],
            preview_url=result["preview_url"],
            review_report=review_report,
            workflow_trace=result["workflow_trace"],
        )
        result["history_item"] = history_item

        if not evaluation.passed:
            result["error"] = evaluation.summary
            self._send(*_json_bytes(result, HTTPStatus.BAD_REQUEST))
            return

        self._send(*_json_bytes(result))

    def _handle_generate(self) -> None:
        (
            _,
            subject,
            grade,
            title,
            class_hour,
            material,
            class_type,
            teaching_style,
            student_level,
            generation_depth,
            strict_ai,
            creative_mode,
            template_path,
            template_analysis,
        ) = self._read_lesson_form()

        request = LessonRequest(
            subject,
            grade,
            title,
            class_hour,
            material,
            class_type,
            teaching_style,
            student_level,
            generation_depth,
            strict_ai,
            creative_mode,
        )
        workflow = TeacherWorkflow(history_db=HISTORY_DB)
        draft_result = workflow.draft(request, template_path, _template_id_for(template_path), template_analysis)
        export_result = workflow.export_document(draft_result["fields"], template_path, OUTPUT_DIR, PREVIEW_DIR)
        output_path = OUTPUT_DIR / str(export_result.get("output_name") or "")
        evaluation = evaluate_lesson_output(
            fields=draft_result["fields"],
            output_path=output_path,
            download_url=export_result.get("download_url"),
            template_analysis=export_result.get("template_analysis"),
            fill_report=export_result.get("fill_report"),
        )
        template_mode = export_result["template_analysis"].get("mode", "unknown")
        export_result["workflow_trace"].append(
            {
                "node": "history_store",
                "label": "历史记录",
                "status": "done",
                "detail": "已写入本地 SQLite 历史库，便于教师找回最近导出。",
                "elapsed_ms": export_result["workflow_trace"][-1]["elapsed_ms"] if export_result["workflow_trace"] else 0,
            }
        )
        history_item = HistoryStore(HISTORY_DB).save_document(
            fields=draft_result["fields"],
            request_context=request.to_dict(),
            generation_backend=str(draft_result["generation_backend"]),
            template_mode=template_mode,
            output_name=export_result["output_name"],
            download_url=export_result["download_url"],
            preview_url=export_result["preview_url"],
            review_report=draft_result["review_report"],
            workflow_trace=export_result["workflow_trace"],
        )

        payload = {
            **draft_result,
            "template_fields": template_analysis["mapped_fields"],
            "template_analysis": export_result["template_analysis"],
            "output_name": export_result["output_name"],
            "download_url": export_result["download_url"],
            "preview_url": export_result["preview_url"],
            "fill_report": export_result.get("fill_report"),
            "evaluation_report": evaluation.to_dict(),
            "workflow_trace": export_result["workflow_trace"],
            "history_item": history_item,
            "llm_status": check_generation_health(probe=False).to_dict(),
        }
        if not evaluation.passed:
            payload["error"] = evaluation.summary
            self._send(*_json_bytes(payload, HTTPStatus.BAD_REQUEST))
            return
        self._send(*_json_bytes(payload))

    def _save_template(self, form: cgi.FieldStorage, allow_sample: bool = False) -> Path:
        template_item = form["template"] if "template" in form else None
        if template_item is None or not template_item.filename:
            if allow_sample:
                if not SAMPLE_TEMPLATE.exists():
                    create_sample_template(SAMPLE_TEMPLATE)
                return SAMPLE_TEMPLATE
            raise ValueError("请上传学校 Word 模板")

        original_name = Path(template_item.filename).name
        if not original_name.lower().endswith(".docx"):
            raise ValueError("请上传 .docx 模板")

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        upload_name = f"{time.strftime('%Y%m%d-%H%M%S')}-{_safe_filename(original_name, 'template.docx')}"
        upload_path = UPLOAD_DIR / upload_name
        with upload_path.open("wb") as file:
            file.write(template_item.file.read())
        return upload_path


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    if not SAMPLE_TEMPLATE.exists():
        create_sample_template(SAMPLE_TEMPLATE)

    server = ThreadingHTTPServer((host, port), TeacherAgentHandler)
    print(f"教案助手 Teacher Skill 已启动：http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("教案助手 Teacher Skill 已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
