from __future__ import annotations

import re
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import teacher_agent.web_app as web_app
from teacher_agent.agent_core.task_router import route_task
from tests.test_uploaded_template_stm32_teaching_method_cell import (
    AGENT_REQUEST,
    _docx_text,
    _make_complex_template,
    _patch_web_paths,
    _post_json,
    _post_multipart,
)


def _run_e2e(
    monkeypatch,
    tmp_path: Path,
    *,
    template_mode: str,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    output_dir = _patch_web_paths(monkeypatch, tmp_path)
    files: dict[str, tuple[str, bytes, str]] = {}
    if template_mode == "upload":
        template = _make_complex_template(tmp_path)
        files = {
            "template": (
                template.name,
                template.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        preview_status, preview = _post_json(base_url, "/api/agent-preview", {"agent_request": AGENT_REQUEST})
        assert preview_status == 200, preview
        assert preview["agent_task"]["grade"] == "24级物联网班"

        run_status, data = _post_multipart(
            base_url,
            "/api/agent-run",
            {
                "agent_request": AGENT_REQUEST,
                "template_mode": template_mode,
                "strict_ai": "0",
            },
            files,
        )
        assert run_status == 200, data
        assert data["fields"]["grade"] == "24级物联网班"
        assert data["fields"]["class_name"] == "24级物联网班"

        export_status, export = _post_json(
            base_url,
            "/api/export",
            {
                "template_id": data["template_id"],
                "fields": data["fields"],
                "request_context": data.get("agent_task") or {},
                "generation_backend": data.get("generation_backend"),
            },
        )
        assert export_status == 200, export
        output_path = output_dir / export["output_name"]
        assert output_path.exists(), export
        return output_path, export, data
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_route_task_preserves_explicit_class_name():
    task = route_task(AGENT_REQUEST)
    assert task.grade == "24级物联网班"
    assert "24物联网1班" not in task.grade


def test_system_template_preserves_explicit_class_name(monkeypatch, tmp_path):
    output_path, _export, _data = _run_e2e(monkeypatch, tmp_path, template_mode="system")
    compact = re.sub(r"\s+", " ", _docx_text(output_path))
    assert "24级物联网班" in compact
    assert "24物联网1班" not in compact
    assert "24 物联网 1 班" not in compact


def test_uploaded_template_preserves_explicit_class_name(monkeypatch, tmp_path):
    output_path, _export, _data = _run_e2e(monkeypatch, tmp_path, template_mode="upload")
    compact = re.sub(r"\s+", " ", _docx_text(output_path))
    assert "24级物联网班" in compact
    assert "24物联网1班" not in compact
    assert "24 物联网 1 班" not in compact
