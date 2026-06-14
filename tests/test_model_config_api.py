from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer

import teacher_agent.deepseek_client as deepseek_client
import teacher_agent.web_app as web_app


API_KEY = "sk-test-secret-abcd"


def _request(base_url: str, path: str, *, method: str = "GET", payload: dict | None = None):
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8") or "{}")


def test_model_config_api_saves_masks_and_clears_without_restart(monkeypatch, tmp_path):
    monkeypatch.setattr(deepseek_client, "MODEL_CONFIG_PATH", tmp_path / ".teacher_skill_config.json")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"

    try:
        status, initial = _request(base_url, "/api/config/model")
        assert status == 200
        assert initial["configured"] is False
        assert "api_key" not in initial

        status, saved = _request(
            base_url,
            "/api/config/model",
            method="POST",
            payload={
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "api_key": API_KEY,
            },
        )
        assert status == 200, saved
        assert saved["configured"] is True
        assert saved["masked_api_key"] == "sk-****abcd"
        assert API_KEY not in json.dumps(saved)

        persisted = (tmp_path / ".teacher_skill_config.json").read_text(encoding="utf-8")
        assert API_KEY in persisted

        status, health = _request(base_url, "/api/model/health")
        assert status == 200
        assert health["configured"] is True
        assert health["model"] == "deepseek-chat"

        status, public_config = _request(base_url, "/api/config/model")
        assert status == 200
        assert public_config["masked_api_key"] == "sk-****abcd"
        assert API_KEY not in json.dumps(public_config)

        status, cleared = _request(base_url, "/api/config/model", method="DELETE")
        assert status == 200
        assert cleared["configured"] is False
        assert not (tmp_path / ".teacher_skill_config.json").exists()

        status, health = _request(base_url, "/api/model/health")
        assert status == 200
        assert health["configured"] is False
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_model_config_test_endpoint_never_returns_full_key(monkeypatch, tmp_path):
    monkeypatch.setattr(deepseek_client, "MODEL_CONFIG_PATH", tmp_path / ".teacher_skill_config.json")

    def fake_test(config):
        assert config["api_key"] == API_KEY
        return {
            "configured": True,
            "ok": True,
            "provider": "deepseek",
            "base_url": config["base_url"],
            "model": config["model"],
            "masked_api_key": "sk-****abcd",
            "status": "ok",
            "message": "连接正常。",
            "error_type": "",
        }

    monkeypatch.setattr(deepseek_client, "test_model_config", fake_test, raising=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), web_app.TeacherAgentHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        status, result = _request(
            base_url,
            "/api/config/model/test",
            method="POST",
            payload={
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "api_key": API_KEY,
            },
        )
        assert status == 200, result
        assert result["ok"] is True
        assert API_KEY not in json.dumps(result)
        assert "api_key" not in result
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_local_model_config_is_gitignored():
    gitignore = open(".gitignore", encoding="utf-8").read()
    assert ".teacher_skill_config.json" in gitignore


def test_concurrent_model_config_saves_leave_valid_masked_config(monkeypatch, tmp_path):
    config_path = tmp_path / ".teacher_skill_config.json"
    monkeypatch.setattr(deepseek_client, "MODEL_CONFIG_PATH", config_path)

    def save(index: int) -> dict:
        return deepseek_client.save_model_config(
            {
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com",
                "model": f"deepseek-model-{index}",
                "api_key": f"sk-concurrent-secret-{index:04d}",
            }
        )

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(save, range(40)))

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["model"].startswith("deepseek-model-")
    assert persisted["api_key"].startswith("sk-concurrent-secret-")
    assert all("api_key" not in result for result in results)
    assert all("sk-concurrent-secret-" not in json.dumps(result) for result in results)
    assert not config_path.with_suffix(config_path.suffix + ".tmp").exists()
