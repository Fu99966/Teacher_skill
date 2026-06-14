from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .atomic_json import atomic_write_json, json_path_lock, read_json


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"
MODEL_CONFIG_PATH = PROJECT_ROOT / ".teacher_skill_config.json"


@dataclass
class DeepSeekStatus:
    configured: bool
    ok: bool
    base_url: str
    model: str
    status: str
    message: str
    error_code: str = ""
    error_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeepSeekError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "",
        error_type: str = "unknown",
        user_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_type = error_type
        self.user_message = user_message or message

    def to_dict(self) -> dict[str, str]:
        return {
            "error_code": self.error_code,
            "error_type": self.error_type,
            "message": self.user_message,
        }


def load_local_env(path: str | Path | None = None) -> None:
    env_path = Path(path) if path else PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_saved_model_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path else MODEL_CONFIG_PATH
    try:
        value = read_json(config_path, {})
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def mask_api_key(api_key: str) -> str:
    value = str(api_key or "").strip()
    if not value:
        return ""
    prefix = "sk-" if value.startswith("sk-") else ""
    suffix = value[-4:] if len(value) >= 4 else value
    return f"{prefix}****{suffix}"


def _validate_model_config(config: dict[str, Any], *, require_key: bool = True) -> dict[str, Any]:
    provider = str(config.get("provider") or "deepseek").strip().lower()
    base_url = str(config.get("base_url") or DEFAULT_BASE_URL).strip().rstrip("/")
    model = str(config.get("model") or DEFAULT_MODEL).strip()
    api_key = str(config.get("api_key") or "").strip()
    try:
        timeout = float(config.get("timeout") or os.getenv("DEEPSEEK_TIMEOUT", "60"))
    except (TypeError, ValueError) as exc:
        raise DeepSeekError("请求超时时间必须是数字", error_type="invalid_config") from exc

    parsed = urlparse(base_url)
    if provider != "deepseek":
        raise DeepSeekError("当前仅支持 DeepSeek 提供商", error_type="invalid_config")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise DeepSeekError("Base URL 必须是有效的 http 或 https 地址", error_type="invalid_config")
    if not model:
        raise DeepSeekError("模型名称不能为空", error_type="invalid_config")
    if require_key and not api_key:
        raise DeepSeekError("请填写 DeepSeek API Key", error_type="not_configured")
    if timeout <= 0:
        raise DeepSeekError("请求超时时间必须大于 0", error_type="invalid_config")
    return {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "api_key": api_key,
        "timeout": timeout,
    }


def _effective_model_config(override: dict[str, Any] | None = None) -> dict[str, Any]:
    load_local_env()
    saved = load_saved_model_config()
    incoming = override or {}
    return _validate_model_config(
        {
            "provider": incoming.get("provider") or saved.get("provider") or "deepseek",
            "base_url": incoming.get("base_url")
            or saved.get("base_url")
            or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL),
            "model": incoming.get("model")
            or saved.get("model")
            or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL),
            "api_key": incoming.get("api_key")
            or saved.get("api_key")
            or os.getenv("DEEPSEEK_API_KEY", ""),
            "timeout": incoming.get("timeout")
            or saved.get("timeout")
            or os.getenv("DEEPSEEK_TIMEOUT", "60"),
        },
        require_key=False,
    )


def get_model_config_public() -> dict[str, Any]:
    config = _effective_model_config()
    api_key = str(config.get("api_key") or "")
    return {
        "configured": bool(api_key),
        "provider": config["provider"],
        "base_url": config["base_url"],
        "model": config["model"],
        "masked_api_key": mask_api_key(api_key),
        "source": "local" if load_saved_model_config() else ("environment" if api_key else "default"),
    }


def save_model_config(config: dict[str, Any]) -> dict[str, Any]:
    with json_path_lock(MODEL_CONFIG_PATH):
        existing = load_saved_model_config()
        merged = dict(existing)
        merged.update({key: value for key, value in config.items() if value not in {None, ""}})
        validated = _validate_model_config(merged, require_key=True)
        atomic_write_json(MODEL_CONFIG_PATH, validated, indent=2)
    return get_model_config_public()


def clear_model_config() -> dict[str, Any]:
    with json_path_lock(MODEL_CONFIG_PATH):
        if MODEL_CONFIG_PATH.exists():
            MODEL_CONFIG_PATH.unlink()
    return get_model_config_public()


def test_model_config(config: dict[str, Any]) -> dict[str, Any]:
    effective = _effective_model_config(config)
    _validate_model_config(effective, require_key=True)
    status = check_deepseek_health(probe=True, config_override=effective)
    result = status.to_dict()
    result["provider"] = effective["provider"]
    result["masked_api_key"] = mask_api_key(str(effective["api_key"]))
    return result


def is_deepseek_configured() -> bool:
    return bool(_effective_model_config().get("api_key"))


def _config(config_override: dict[str, Any] | None = None) -> tuple[str, str, str, float]:
    config = _effective_model_config(config_override)
    api_key = str(config.get("api_key") or "").strip()
    if not api_key:
        raise DeepSeekError(
            "DEEPSEEK_API_KEY is not configured",
            error_type="not_configured",
            user_message="未配置 DeepSeek API Key，请在网页 API 配置中填写，或继续使用本地初稿。",
        )
    return api_key, str(config["base_url"]), str(config["model"]), float(config["timeout"])


def _extract_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise
        value = json.loads(match.group(0))

    if not isinstance(value, dict):
        raise DeepSeekError(
            "DeepSeek response is not a JSON object",
            error_type="invalid_json",
            user_message="DeepSeek 返回内容不是合法 JSON，请重试或降低生成复杂度。",
        )
    return value


def _classify_http_error(code: int, message: str) -> tuple[str, str]:
    if code == 401:
        return "auth_failed", "API Key 无效或未授权，请检查 .env 中的 DEEPSEEK_API_KEY。"
    if code == 402:
        return "insufficient_balance", "DeepSeek 账户余额不足，请充值后重试。"
    if code in {404, 422}:
        return "bad_request", "模型名或请求参数可能不正确，请检查 DEEPSEEK_MODEL 和接口配置。"
    if code == 429:
        return "rate_limited", "请求过于频繁或并发达到限制，请稍后再试。"
    if code in {500, 502, 503, 504}:
        return "server_error", "DeepSeek 服务暂时不可用或响应超时，请稍后重试。"
    return "http_error", f"DeepSeek API 返回 HTTP {code}：{message[:180]}"


def _safe_http_message(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:500]
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("type") or data)[:500]
    return str(data)[:500]


def chat_json(
    prompt: str,
    *,
    system: str,
    temperature: float = 0.75,
    max_tokens: int = 6000,
    config_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    api_key, base_url, model, timeout = _config(config_override)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw_message = exc.read().decode("utf-8", errors="replace")
        message = _safe_http_message(raw_message)
        error_type, user_message = _classify_http_error(exc.code, message)
        raise DeepSeekError(
            f"DeepSeek API HTTP {exc.code}: {message}",
            error_code=str(exc.code),
            error_type=error_type,
            user_message=user_message,
        ) from exc
    except urllib.error.URLError as exc:
        raise DeepSeekError(
            f"DeepSeek API request failed: {exc.reason}",
            error_type="network_error",
            user_message=f"无法连接 DeepSeek API：{exc.reason}。请检查网络、代理或 DEEPSEEK_BASE_URL。",
        ) from exc

    data = json.loads(raw)
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError(
            "DeepSeek API response missing message content",
            error_type="invalid_response",
            user_message="DeepSeek 返回结构异常，未找到 message.content。",
        ) from exc

    return _extract_json_object(str(content))


def check_deepseek_health(
    probe: bool = False,
    config_override: dict[str, Any] | None = None,
) -> DeepSeekStatus:
    config = _effective_model_config(config_override)
    base_url = str(config["base_url"])
    model = str(config["model"])
    configured = bool(config.get("api_key"))
    if not configured:
        return DeepSeekStatus(
            configured=False,
            ok=False,
            base_url=base_url,
            model=model,
            status="not_configured",
            message="未配置 DEEPSEEK_API_KEY，当前无法调用真实 AI 生成。",
            error_type="not_configured",
        )

    if not probe:
        return DeepSeekStatus(
            configured=True,
            ok=True,
            base_url=base_url,
            model=model,
            status="configured",
            message="已检测到 DeepSeek 配置。点击诊断或生成时会发起真实请求。",
        )

    try:
        chat_json(
            "请只输出 JSON：{\"ok\": true}",
            system="你是健康检查接口，只输出合法 JSON。",
            temperature=0,
            max_tokens=64,
            config_override=config,
        )
        return DeepSeekStatus(
            configured=True,
            ok=True,
            base_url=base_url,
            model=model,
            status="ok",
            message="DeepSeek 连接正常。",
        )
    except DeepSeekError as exc:
        return DeepSeekStatus(
            configured=True,
            ok=False,
            base_url=base_url,
            model=model,
            status="error",
            message=exc.user_message,
            error_code=exc.error_code,
            error_type=exc.error_type,
        )
