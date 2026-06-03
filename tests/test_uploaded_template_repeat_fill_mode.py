from __future__ import annotations

import re
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from docx import Document

import teacher_agent.web_app as web_app
from tests.test_uploaded_template_stm32_teaching_method_cell import (
    AGENT_REQUEST,
    _docx_text,
    _make_complex_template,
    _parallel_heading_cells,
    _patch_web_paths,
    _post_json,
    _post_multipart,
)


def _run_uploaded_export(
    monkeypatch,
    tmp_path: Path,
    *,
    repeat_fill_mode: str | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
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

        run_fields = {
            "agent_request": AGENT_REQUEST,
            "template_mode": "upload",
            "strict_ai": "0",
        }
        if repeat_fill_mode:
            run_fields["repeat_fill_mode"] = repeat_fill_mode

        run_status, data = _post_multipart(
            base_url,
            "/api/agent-run",
            run_fields,
            {
                "template": (
                    template.name,
                    template.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert run_status == 200, data

        export_payload: dict[str, Any] = {
            "template_id": data["template_id"],
            "fields": data["fields"],
            "request_context": data.get("agent_task") or {},
            "generation_backend": data.get("generation_backend"),
        }
        if repeat_fill_mode:
            export_payload["repeat_fill_mode"] = repeat_fill_mode

        export_status, export = _post_json(base_url, "/api/export", export_payload)
        assert export_status == 200, export
        output_path = output_dir / export["output_name"]
        assert output_path.exists(), export
        return output_path, export, data
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _method_hits(text: str) -> int:
    return sum(
        keyword in text
        for keyword in ["项目教学法", "任务驱动法", "演示教学法", "分组协作", "巡回指导", "作品展示评价"]
    )


def _section_cells(path: Path) -> list[tuple[str, str]]:
    return [(process_cell.text, method_cell.text) for process_cell, method_cell in _parallel_heading_cells(Document(str(path)))]


def test_repeat_fill_mode_defaults_to_first_only_for_uploaded_templates(monkeypatch, tmp_path):
    output_path, export, data = _run_uploaded_export(monkeypatch, tmp_path)

    assert data["fields"]["class_name"] == "24级物联网班"
    text = _docx_text(output_path)
    compact = re.sub(r"\s+", " ", text)
    assert "STM32智能小车课程" in compact or "STM32 智能小车课程" in compact
    assert "24级物联网班" in compact
    assert "24物联网1班" not in compact

    cells = _section_cells(output_path)
    assert len(cells) == 2
    first_process, first_method = cells[0]
    second_process, second_method = cells[1]

    for keyword in ["STM32", "PWM", "电机驱动", "循迹", "避障"]:
        assert keyword in first_process
    assert _method_hits(first_method) >= 4

    assert "本项目共32课时" not in second_process
    assert "STM32" not in second_process
    assert _method_hits(second_method) == 0

    fill_report = export["fill_report"]
    assert fill_report["repeated_sections_detected"] == 2
    assert fill_report["repeat_fill_mode"] == "first_only"
    assert fill_report["filled_sections"] == 1
    assert fill_report["field_write_counts"]["teaching_method"] == 1


def test_repeat_fill_mode_all_fills_every_repeated_template(monkeypatch, tmp_path):
    output_path, export, _data = _run_uploaded_export(monkeypatch, tmp_path, repeat_fill_mode="all")

    cells = _section_cells(output_path)
    assert len(cells) == 2
    passed_sections = 0
    for process_text, method_text in cells:
        process_ok = all(
            keyword in process_text
            for keyword in ["本项目共32课时", "STM32", "智能小车", "PWM", "电机驱动", "循迹", "避障"]
        )
        if process_ok and _method_hits(method_text) >= 4:
            passed_sections += 1

    assert passed_sections == 2
    fill_report = export["fill_report"]
    assert fill_report["repeated_sections_detected"] == 2
    assert fill_report["repeat_fill_mode"] == "all"
    assert fill_report["filled_sections"] == 2
    assert fill_report["field_write_counts"]["teaching_method"] >= 2
