from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

from docx import Document

import teacher_agent.web_app as web_app
from test_uploaded_template_stm32_teaching_method_cell import (
    AGENT_REQUEST,
    _make_complex_template,
    _parallel_heading_cells,
    _patch_web_paths,
    _post_json,
    _post_multipart,
)


def test_uploaded_template_uses_compact_teaching_method_in_narrow_cell(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    output_dir = _patch_web_paths(monkeypatch, tmp_path)
    template = _make_complex_template(tmp_path)

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        preview_status, preview = _post_json(base_url, "/api/agent-preview", {"agent_request": AGENT_REQUEST})
        assert preview_status == 200, preview

        run_status, data = _post_multipart(
            base_url,
            "/api/agent-run",
            {
                "agent_request": AGENT_REQUEST,
                "template_mode": "upload",
                "strict_ai": "0",
                "repeat_fill_mode": "first_only",
            },
            {
                "template": (
                    template.name,
                    template.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert run_status == 200, data

        export_status, export = _post_json(
            base_url,
            "/api/export",
            {
                "template_id": data["template_id"],
                "fields": data["fields"],
                "request_context": data.get("agent_task") or {},
                "generation_backend": data.get("generation_backend"),
                "repeat_fill_mode": "first_only",
            },
        )
        assert export_status == 200, export
        output_path = output_dir / export["output_name"]

        populated_methods = [
            method_cell.text.strip()
            for _process_cell, method_cell in _parallel_heading_cells(Document(str(output_path)))
            if method_cell.text.strip()
        ]
        assert len(populated_methods) == 1
        method_text = populated_methods[0]
        assert len(method_text) <= 120
        for keyword in ["项目教学法", "任务驱动法", "演示教学法", "巡回指导", "作品展示评价"]:
            assert keyword in method_text
        assert "学生在真实智能小车项目实践中完成设计、检查、修改和展示" not in method_text
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
