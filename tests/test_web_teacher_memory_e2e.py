from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import teacher_agent.web_app as web_app


PROMPT = "帮我生成一份24级物联网班《传感器基础》的实验课教案，课时2课时。"
OTHER_PROMPT = "帮我生成一份24级物联网班《物联网通信基础》的实验课教案，课时2课时。"


def _open_json(request: urllib.request.Request) -> tuple[int, dict[str, Any]]:
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8", errors="replace") or "{}")


def _post_json(base_url: str, path: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        base_url + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return _open_json(request)


def _post_agent_run(base_url: str, prompt: str) -> tuple[int, dict[str, Any]]:
    boundary = "----teacher-memory-" + uuid.uuid4().hex
    fields = {
        "agent_request": prompt,
        "template_mode": "system",
        "strict_ai": "0",
    }
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
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    request = urllib.request.Request(
        base_url + "/api/agent-run",
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    return _open_json(request)


def _patch_paths(monkeypatch, tmp_path: Path) -> None:
    output_dir = tmp_path / "outputs"
    template_dir = tmp_path / "templates"
    monkeypatch.setattr(web_app, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(web_app, "UPLOAD_DIR", output_dir / "uploads")
    monkeypatch.setattr(web_app, "PREVIEW_DIR", output_dir / "previews")
    monkeypatch.setattr(web_app, "HISTORY_DB", output_dir / "history.sqlite3")
    monkeypatch.setattr(web_app, "AGENT_MEMORY_DB", output_dir / "memory.sqlite3")
    monkeypatch.setattr(web_app, "TEMPLATE_DIR", template_dir)
    monkeypatch.setattr(web_app, "SAMPLE_TEMPLATE", template_dir / "sample_lesson_template.docx")


def test_web_remember_edit_changes_next_same_lesson_but_not_other_lesson(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.setattr("teacher_agent.lesson_generator.is_deepseek_configured", lambda: False)
    _patch_paths(monkeypatch, tmp_path)

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        first_status, first = _post_agent_run(base_url, PROMPT)
        assert first_status == 200, first
        edited_fields = dict(first["fields"])
        edited_fields["teaching_process"] = "老师确认后的证据链实验过程：观察、记录、解释、互评。"
        edited_fields["teaching_method"] = "问题链驱动法、实验探究法、同伴互评。"
        edited_fields["homework"] = "提交传感器证据链实验报告。"

        remember_status, remembered = _post_json(
            base_url,
            "/api/remember-edit",
            {
                "template_id": first["template_id"],
                "request_context": first["agent_task"],
                "fields": edited_fields,
            },
        )
        assert remember_status == 200, remembered
        assert remembered["ok"] is True

        same_status, same = _post_agent_run(base_url, PROMPT)
        assert same_status == 200, same
        assert same["fields"]["teaching_process"] == edited_fields["teaching_process"]
        assert same["fields"]["teaching_method"] == edited_fields["teaching_method"]
        assert same["fields"]["homework"] == edited_fields["homework"]
        assert same["fields"]["lesson_title"] == "传感器基础"

        other_status, other = _post_agent_run(base_url, OTHER_PROMPT)
        assert other_status == 200, other
        assert other["fields"]["lesson_title"] == "物联网通信基础"
        assert edited_fields["teaching_process"] not in other["fields"]["teaching_process"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
