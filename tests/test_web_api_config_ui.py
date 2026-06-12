from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_contains_safe_model_config_dialog():
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "static" / "app.js").read_text(encoding="utf-8")

    for text in ("API 配置", "Base URL", "Model", "API Key", "测试连接", "保存配置", "清除配置"):
        assert text in html
    assert 'id="model-api-key"' in html
    assert 'type="password"' in html
    assert "/api/config/model" in script
    assert "/api/config/model/test" in script
    assert "masked_api_key" in script
    assert "localStorage.setItem" not in script
