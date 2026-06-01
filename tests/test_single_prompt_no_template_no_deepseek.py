from __future__ import annotations

import json
import threading
import uuid
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import teacher_agent.web_app as web_app


PROMPT = (
    "\u5e2e\u6211\u751f\u6210\u4e00\u4efd 24\u7269\u8054\u7f511\u73ed"
    "\u300aPCB\u677f\u8bbe\u8ba1\u300b\u7684\u5b9e\u8bad\u8bfe\u6559\u6848"
    "\uff0c\u9002\u5408\u9879\u76ee\u5f0f\u6559\u5b66\uff0c\u8bfe\u65f632\u8bfe\u65f6\u3002"
)


def _post_json(base_url: str, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base_url + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _open_json(request)


def _post_multipart(base_url: str, path: str, fields: dict[str, str]) -> tuple[int, dict[str, Any]]:
    boundary = "----teacher-skill-test-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    body = b"".join(chunks)
    request = urllib.request.Request(
        base_url + path,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return _open_json(request)


def _open_json(request: urllib.request.Request) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            data = {"error": raw}
        return exc.code, data


def _patch_web_paths(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    upload_dir = output_dir / "uploads"
    preview_dir = output_dir / "previews"
    template_dir = tmp_path / "templates"
    sample_template = template_dir / "sample_lesson_template.docx"
    monkeypatch.setattr(web_app, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(web_app, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(web_app, "PREVIEW_DIR", preview_dir)
    monkeypatch.setattr(web_app, "HISTORY_DB", output_dir / "history.sqlite3")
    monkeypatch.setattr(web_app, "AGENT_MEMORY_DB", output_dir / "memory.sqlite3")
    monkeypatch.setattr(web_app, "TEMPLATE_DIR", template_dir)
    monkeypatch.setattr(web_app, "SAMPLE_TEMPLATE", sample_template)


def test_single_prompt_without_template_or_deepseek_uses_system_template_and_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    _patch_web_paths(monkeypatch, tmp_path)

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        preview_status, preview = _post_json(base_url, "/api/agent-preview", {"agent_request": PROMPT})
        assert preview_status == 200, preview
        agent_task = preview["agent_task"]
        assert agent_task["title"] == "PCB\u677f\u8bbe\u8ba1"
        assert agent_task["grade"] == "24\u7269\u8054\u7f511\u73ed"
        assert "32" in agent_task["class_hour"]
        assert not preview.get("missing_fields")

        run_status, data = _post_multipart(
            base_url,
            "/api/agent-run",
            {
                "agent_request": PROMPT,
                "template_mode": "system",
                "strict_ai": "0",
            },
        )
        assert run_status == 200, data
        assert data.get("generation_backend") != "deepseek_strict_failed"
        assert data.get("generation_backend") == "local_fallback"
        assert data.get("template_mode") == "system"

        fields = data.get("fields") or {}
        assert fields, data
        assert fields.get("lesson_title") or fields.get("\u8bfe\u9898")
        assert "32" in str(fields.get("class_hour") or fields.get("\u8bfe\u65f6") or "")

        process = fields.get("teaching_process") or fields.get("\u4e3b\u8981\u6559\u5b66\u5185\u5bb9") or ""
        assert "\u9879\u76ee" in process
        assert "\u9636\u6bb5" in process
        assert "\u8bfe\u65f6\u5206\u914d" in process

        method = fields.get("teaching_method") or fields.get("\u6559\u5b66\u65b9\u6cd5\u7684\u8fd0\u7528") or ""
        assert "\u9879\u76ee\u6559\u5b66\u6cd5" in method or "\u4efb\u52a1\u9a71\u52a8" in method

        download_url = data.get("download_url")
        if not download_url:
            export_status, export = _post_json(
                base_url,
                "/api/export",
                {
                    "template_id": data["template_id"],
                    "fields": fields,
                    "request_context": data.get("agent_task") or {},
                    "generation_backend": data.get("generation_backend"),
                },
            )
            assert export_status == 200, export
            download_url = export.get("download_url")

        assert download_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
