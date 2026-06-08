from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

from docx import Document

import teacher_agent.web_app as web_app
from teacher_agent.docx_filler import COMPACT_TEACHING_METHOD
from test_uploaded_template_stm32_teaching_method_cell import (
    AGENT_REQUEST,
    _make_complex_template,
    _parallel_heading_cells,
    _patch_web_paths,
    _post_json,
    _post_multipart,
)


USER_EDITED_METHOD = (
    "项目教学法、任务驱动法。"
    "学生在真实智能小车项目实践中完成设计、检查、修改和展示。"
)


def test_uploaded_template_compacts_user_edited_method_for_narrow_cell(monkeypatch, tmp_path):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    output_dir = _patch_web_paths(monkeypatch, tmp_path)
    template = _make_complex_template(tmp_path)

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        preview_status, preview = _post_json(
            base_url,
            "/api/agent-preview",
            {"agent_request": AGENT_REQUEST},
        )
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

        fields = dict(data["fields"])
        fields["teaching_method"] = USER_EDITED_METHOD
        assert len(USER_EDITED_METHOD) < 80

        export_status, export = _post_json(
            base_url,
            "/api/export",
            {
                "template_id": data["template_id"],
                "fields": fields,
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
        assert populated_methods == [COMPACT_TEACHING_METHOD]
        assert len(populated_methods[0]) <= 120
        assert "学生在真实智能小车项目实践中完成设计、检查、修改和展示" not in populated_methods[0]
        assert export["output_quality_report"]["checks"]["teaching_method_fit_for_narrow_cell"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
