from __future__ import annotations

import http.client
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import teacher_agent.web_app as web_app

PROJECT_ROOT = web_app.PROJECT_ROOT


def _open(request: urllib.request.Request) -> tuple[int, dict, dict]:
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}"), dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8", errors="replace") or "{}"), dict(exc.headers)


def _post_json(base_url: str, payload: dict, origin: str) -> tuple[int, dict, dict]:
    return _open(
        urllib.request.Request(
            base_url + "/api/agent-preview",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Origin": origin},
            method="POST",
        )
    )


def test_mutating_api_allows_same_origin_and_rejects_external_origin():
    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    payload = {"agent_request": "帮我生成一份24级物联网班《传感器基础》的实验课教案。"}

    try:
        allowed_status, allowed, allowed_headers = _post_json(base_url, payload, base_url)
        assert allowed_status == 200, allowed
        assert allowed_headers.get("Access-Control-Allow-Origin") == base_url

        blocked_status, blocked, blocked_headers = _post_json(base_url, payload, "https://evil.example")
        assert blocked_status == 403, blocked
        assert "只允许" in blocked["error"]
        assert blocked_headers.get("Access-Control-Allow-Origin") is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cross_origin_preflight_is_rejected():
    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload, headers = _open(
            urllib.request.Request(
                base_url + "/api/config/model",
                headers={"Origin": "https://evil.example"},
                method="OPTIONS",
            )
        )
        assert status == 403, payload
        assert headers.get("Access-Control-Allow-Origin") is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_oversized_post_is_rejected_before_body_parsing(monkeypatch):
    monkeypatch.setattr(web_app, "MAX_JSON_REQUEST_BYTES", 32)
    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address

    try:
        connection = http.client.HTTPConnection(host, port, timeout=10)
        connection.request(
            "POST",
            "/api/agent-preview",
            body=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": "1024"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 413, payload
        assert "请求内容过大" in payload["error"]
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cross_origin_get_does_not_expose_wildcard_cors():
    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, payload, headers = _open(
            urllib.request.Request(base_url + "/health", headers={"Origin": "https://evil.example"})
        )
        assert status == 200, payload
        assert headers.get("Access-Control-Allow-Origin") is None
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_browser_validates_upload_size_before_generation():
    app_js = (PROJECT_ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")

    assert "const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;" in app_js
    assert "function validateUploadSize()" in app_js
    assert "本次上传文件总大小超过 50 MB" in app_js
    assert "if (!validateUploadSize()) return;" in app_js
