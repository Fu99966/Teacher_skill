from __future__ import annotations

import cgi
import json
import mimetypes
import re
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from .docx_filler import fill_docx_template
from .lesson_generator import draft_lesson_fields
from .sample_template import create_sample_template
from .template_parser import scan_template


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = PROJECT_ROOT / "web"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
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

        if path == "/download/sample-template":
            if not SAMPLE_TEMPLATE.exists():
                create_sample_template(SAMPLE_TEMPLATE)
            self._send_file(SAMPLE_TEMPLATE, as_attachment=True)
            return

        if path.startswith("/download/"):
            name = Path(path.removeprefix("/download/")).name
            self._send_file(OUTPUT_DIR / name, as_attachment=True)
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

        self._send(*_json_bytes({"ok": True}), include_body=False)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/generate":
            self._send(*_json_bytes({"error": "接口不存在"}, HTTPStatus.NOT_FOUND))
            return

        try:
            self._handle_generate()
        except Exception as exc:
            self._send(*_json_bytes({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR))

    def _handle_generate(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send(*_json_bytes({"error": "请使用表单提交"}, HTTPStatus.BAD_REQUEST))
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": content_type},
        )

        subject = _form_value(form, "subject", "语文")
        grade = _form_value(form, "grade", "四年级")
        title = _form_value(form, "title", "未命名课题")
        class_hour = _form_value(form, "class_hour", "1课时")
        material = _form_value(form, "material", "")

        template_path = self._save_template(form)
        template_fields = scan_template(template_path)

        lesson = draft_lesson_fields(subject, grade, title, material, class_hour)
        safe_title = _safe_filename(f"{grade}-{subject}-{title}-教案")
        output_name = f"{safe_title}-{time.strftime('%Y%m%d-%H%M%S')}.docx"
        output_path = OUTPUT_DIR / output_name
        fill_docx_template(template_path, lesson.to_dict(), output_path)

        self._send(
            *_json_bytes(
                {
                    "fields": lesson.to_dict(),
                    "template_fields": template_fields,
                    "output_name": output_name,
                    "download_url": f"/download/{output_name}",
                }
            )
        )

    def _save_template(self, form: cgi.FieldStorage) -> Path:
        template_item = form["template"] if "template" in form else None
        if template_item is None or not template_item.filename:
            if not SAMPLE_TEMPLATE.exists():
                create_sample_template(SAMPLE_TEMPLATE)
            return SAMPLE_TEMPLATE

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
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    if not SAMPLE_TEMPLATE.exists():
        create_sample_template(SAMPLE_TEMPLATE)

    server = ThreadingHTTPServer((host, port), TeacherAgentHandler)
    print(f"教师文档智能体已启动：http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("教师文档智能体已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
