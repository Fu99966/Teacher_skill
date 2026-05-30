"""Tests for /api/model/health endpoint — no key, configured, probe, auth_failed."""
from __future__ import annotations

import json


def test_health_not_configured(monkeypatch):
    """Without DEEPSEEK_API_KEY, probe=False returns not_configured."""
    from teacher_agent.deepseek_client import check_deepseek_health

    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    status = check_deepseek_health(probe=False)
    assert not status.configured
    assert status.status == "not_configured"
    assert status.error_type == "not_configured"
    assert not status.ok


def test_health_configured_without_probe(monkeypatch):
    """With key but probe=False, returns configured (not actually tested)."""
    from teacher_agent.deepseek_client import check_deepseek_health

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-fake-test-key")

    status = check_deepseek_health(probe=False)
    assert status.configured
    assert status.status == "configured"
    assert status.ok  # not proven, but that's the contract


def test_health_probe_ok(monkeypatch):
    """Mock a successful DeepSeek response for probe=1."""
    from teacher_agent.deepseek_client import check_deepseek_health

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-fake-test-key")

    def _mock_chat_json(*args, **kwargs):
        return {"ok": True}

    monkeypatch.setattr("teacher_agent.deepseek_client.chat_json", _mock_chat_json)

    status = check_deepseek_health(probe=True)
    assert status.configured
    assert status.status == "ok"
    assert status.ok


def test_health_probe_auth_failed(monkeypatch):
    """Mock DeepSeekError with auth_failed — probe=1 returns auth_failed."""
    from teacher_agent.deepseek_client import check_deepseek_health, DeepSeekError

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-invalid")

    def _mock_auth_error(*args, **kwargs):
        raise DeepSeekError(
            "API Key 无效", error_type="auth_failed",
            user_message="API Key 无效或未授权，请检查。"
        )

    monkeypatch.setattr("teacher_agent.deepseek_client.chat_json", _mock_auth_error)

    status = check_deepseek_health(probe=True)
    assert status.configured
    assert status.error_type == "auth_failed"
    assert not status.ok


def test_health_probe_network_error(monkeypatch):
    """Mock DeepSeekError with network_error — probe=1 returns error."""
    from teacher_agent.deepseek_client import check_deepseek_health, DeepSeekError

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    def _mock_network_error(*args, **kwargs):
        raise DeepSeekError(
            "Connection refused", error_type="network_error",
            user_message="无法连接到 DeepSeek 服务器，请检查网络。"
        )

    monkeypatch.setattr("teacher_agent.deepseek_client.chat_json", _mock_network_error)

    status = check_deepseek_health(probe=True)
    assert status.configured
    assert status.error_type == "network_error"
    assert not status.ok


def test_web_api_returns_structured_json(monkeypatch):
    """Verify the web route logic returns all expected fields."""
    from teacher_agent.deepseek_client import check_deepseek_health

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    status = check_deepseek_health(probe=True)
    data = status.to_dict()

    required = ["configured", "status", "model", "message", "base_url", "error_type"]
    for key in required:
        assert key in data, f"Missing key: {key} — got {list(data.keys())}"

    print(f"\n✅ Model health: status={data['status']}, error_type={data.get('error_type')}")
