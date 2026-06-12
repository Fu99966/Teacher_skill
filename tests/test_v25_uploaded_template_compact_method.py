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


def test_v25_uploaded_template_uses_compact_method_in_actual_target_cell(monkeypatch, tmp_path):
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

        cells = list(_parallel_heading_cells(Document(str(output_dir / export["output_name"]))))
        assert len(cells) == 2
        first_process, first_method = cells[0]
        second_process, second_method = cells[1]
        for keyword in ("本项目共32课时", "STM32", "PWM", "电机驱动", "循迹", "避障"):
            assert keyword in first_process.text
        for keyword in ("项目教学法", "任务驱动法", "演示教学法", "巡回指导", "作品展示评价"):
            assert keyword in first_method.text
        assert len(first_method.text.strip()) <= 120
        assert "学生在真实智能小车项目实践中完成设计、检查、修改和展示" not in first_method.text
        assert not second_process.text.strip()
        assert not second_method.text.strip()
        assert export["output_quality_report"]["checks"]["teaching_method_fit_for_narrow_cell"] is True
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
