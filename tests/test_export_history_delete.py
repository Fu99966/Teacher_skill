from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import teacher_agent.web_app as web_app
from teacher_agent.history_store import HistoryStore


def _request(base_url: str, path: str, *, method: str = "GET"):
    request = urllib.request.Request(base_url + path, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def _save_history(store: HistoryStore, output_name: str) -> dict:
    return store.save_document(
        fields={"lesson_title": "测试教案", "subject": "物联网", "grade": "24级物联网班"},
        request_context={},
        generation_backend="local_fallback",
        template_mode="system",
        output_name=output_name,
        download_url=f"/download/{output_name}",
        preview_url=None,
    )


def test_history_delete_removes_output_file_and_sqlite_record(monkeypatch, tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    db_path = output_dir / "history.sqlite3"
    monkeypatch.setattr(web_app, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(web_app, "HISTORY_DB", db_path)
    file_path = output_dir / "lesson.docx"
    file_path.write_bytes(b"docx")
    record = _save_history(HistoryStore(db_path), file_path.name)

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, history = _request(base_url, "/api/history")
        assert status == 200
        assert history["items"][0]["id"] == record["id"]

        status, result = _request(base_url, f"/api/history/{record['id']}", method="DELETE")
        assert status == 200, result
        assert result == {"ok": True, "deleted_file": True, "deleted_history": True}
        assert not file_path.exists()
        assert HistoryStore(db_path).list_documents() == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_history_delete_rejects_output_path_escape(monkeypatch, tmp_path):
    output_dir = tmp_path / "outputs"
    output_dir.mkdir()
    db_path = output_dir / "history.sqlite3"
    outside = tmp_path / "outside.docx"
    outside.write_bytes(b"do-not-delete")
    monkeypatch.setattr(web_app, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(web_app, "HISTORY_DB", db_path)
    record = _save_history(HistoryStore(db_path), "../outside.docx")

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, result = _request(base_url, f"/api/history/{record['id']}", method="DELETE")
        assert status == 400, result
        assert result["ok"] is False
        assert outside.exists()
        assert HistoryStore(db_path).list_documents()

        missing_status, missing = _request(base_url, "/api/history/not-found", method="DELETE")
        assert missing_status == 404
        assert missing["ok"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
