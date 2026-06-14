from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

import teacher_agent.web_app as web_app


def _text_pdf_bytes(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    stream = DecodedStreamObject()
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _multipart_request(
    base_url: str,
    path: str,
    fields: dict[str, str],
    *,
    file_name: str,
    file_bytes: bytes,
) -> urllib.request.Request:
    boundary = "----teacher-skill-pdf-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("ascii"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("ascii"),
            (
                'Content-Disposition: form-data; name="material_file"; '
                f'filename="{file_name}"\r\n'
            ).encode("utf-8"),
            b"Content-Type: application/pdf\r\n\r\n",
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("ascii"),
        ]
    )
    return urllib.request.Request(
        base_url + path,
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )


def _open_json(request: urllib.request.Request) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8", errors="replace") or "{}")


def _patch_web_paths(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    template_dir = tmp_path / "templates"
    monkeypatch.setattr(web_app, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(web_app, "UPLOAD_DIR", output_dir / "uploads")
    monkeypatch.setattr(web_app, "PREVIEW_DIR", output_dir / "previews")
    monkeypatch.setattr(web_app, "HISTORY_DB", output_dir / "history.sqlite3")
    monkeypatch.setattr(web_app, "AGENT_MEMORY_DB", output_dir / "memory.sqlite3")
    monkeypatch.setattr(web_app, "TEMPLATE_DIR", template_dir)
    monkeypatch.setattr(web_app, "SAMPLE_TEMPLATE", template_dir / "sample_lesson_template.docx")


def test_uploaded_pdf_material_reaches_web_agent_generation(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    _patch_web_paths(monkeypatch, tmp_path)

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        request = _multipart_request(
            base_url,
            "/api/agent-run",
            {
                "agent_request": "帮我生成一份24级物联网班《无线通信基础》的2课时实验课教案。",
                "subject": "物联网",
                "template_mode": "system",
                "strict_ai": "0",
            },
            file_name="wireless-course.pdf",
            file_bytes=_text_pdf_bytes(
                "LoRaWAN gateway MQTT QoS sensor telemetry assessment rubric"
            ),
        )
        status, payload = _open_json(request)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert status == 200, payload
    assert payload["generation_backend"] == "local_fallback"
    extraction = payload["template_analysis"]["material_extraction"]
    assert extraction["source_name"] == "wireless-course.pdf"
    assert extraction["warnings"] == []
    assert "LoRaWAN gateway MQTT QoS" in extraction["text"]

    fields = payload["fields"]
    generated_text = "\n".join(str(value) for value in fields.values())
    assert "LoRaWAN" in generated_text
    assert "MQTT" in generated_text
    assert "资料聚焦" in fields["teaching_process"]
