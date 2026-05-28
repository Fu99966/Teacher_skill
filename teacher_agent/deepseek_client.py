from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"


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


def is_deepseek_configured() -> bool:
    load_local_env()
    return bool(os.getenv("DEEPSEEK_API_KEY"))


def _config() -> tuple[str, str, str, float]:
    load_local_env()
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise DeepSeekError(
            "DEEPSEEK_API_KEY is not configured",
            error_type="not_configured",
            user_message="未配置 DEEPSEEK_API_KEY，请先在项目根目录创建 .env。",
        )

    base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    timeout = float(os.getenv("DEEPSEEK_TIMEOUT", "60"))
    return api_key, base_url, model, timeout


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


def chat_json(prompt: str, *, system: str, temperature: float = 0.75, max_tokens: int = 6000) -> dict[str, Any]:
    api_key, base_url, model, timeout = _config()
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


def check_deepseek_health(probe: bool = False) -> DeepSeekStatus:
    load_local_env()
    base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/") or DEFAULT_BASE_URL
    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    configured = bool(os.getenv("DEEPSEEK_API_KEY"))
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
