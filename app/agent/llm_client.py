from __future__ import annotations

import json
import time
from os import environ
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_RETRY_STATUS = frozenset({408, 429, 500, 502, 503, 504})
_DEFAULT_TIMEOUT = 45.0
_DEFAULT_RETRIES = 2
_MAX_BACKOFF = 8.0


class LlmClient(Protocol):
    def available(self) -> bool: ...

    def complete(self, *, system: str, user: str) -> Any: ...


class UnconfiguredLlmClient:
    """无密钥：不发请求。Parser 直接走规则，不算失败 fallback。"""

    def available(self) -> bool:
        return False

    def complete(self, *, system: str, user: str) -> Any:
        raise RuntimeError("llm_unconfigured")


class FakeLlmClient:
    """测试用。禁止连接真实模型。"""

    def __init__(
        self,
        responses: dict[str, Any] | None = None,
        *,
        default: Any = None,
        error: Exception | None = None,
    ) -> None:
        self._responses = responses or {}
        self._default = default
        self._error = error

    def available(self) -> bool:
        return True

    def complete(self, *, system: str, user: str) -> Any:
        if self._error is not None:
            raise self._error
        if user in self._responses:
            return self._responses[user]
        if self._default is not None:
            return self._default
        raise LookupError(f"no fake LLM payload for {user!r}")


class HttpLlmClient:
    """OpenAI 兼容 Chat Completions。只抽语言，不带业务上下文。"""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = _DEFAULT_TIMEOUT,
        retries: int = _DEFAULT_RETRIES,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout
        self._retries = max(0, int(retries))
        self._sleep = sleep or time.sleep

    def available(self) -> bool:
        return True

    def complete(self, *, system: str, user: str) -> Any:
        last_exc: Exception | None = None
        attempts = self._retries + 1
        for attempt in range(attempts):
            try:
                return self._post(system=system, user=user)
            except Exception as exc:
                last_exc = exc
                if isinstance(exc, HTTPError):
                    _drain_http_error(exc)
                label = _client_error_label(exc)
                if not _retryable(exc) or attempt + 1 >= attempts:
                    if isinstance(exc, RuntimeError) and str(exc).startswith("client_error"):
                        raise
                    raise RuntimeError(label) from exc
                self._sleep(_backoff(exc, attempt))
        raise RuntimeError(_client_error_label(last_exc)) from last_exc

    def _post(self, *, system: str, user: str) -> Any:
        url = self.base_url + "/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=self._timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("client_error:invalid_response") from exc


def client_from_env() -> LlmClient:
    api_key = (environ.get("LLM_API_KEY") or "").strip()
    if not api_key:
        return UnconfiguredLlmClient()
    base_url = (environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").strip()
    model = (environ.get("LLM_MODEL") or "gpt-4o-mini").strip()
    timeout = _positive_float(environ.get("LLM_TIMEOUT"), _DEFAULT_TIMEOUT)
    retries = _positive_int(environ.get("LLM_RETRIES"), _DEFAULT_RETRIES)
    return HttpLlmClient(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout=timeout,
        retries=retries,
    )


def _positive_float(raw: str | None, default: float) -> float:
    text = (raw or "").strip()
    if not text:
        return default
    try:
        value = float(text)
    except ValueError:
        return default
    return value if value > 0 else default


def _positive_int(raw: str | None, default: int) -> int:
    text = (raw or "").strip()
    if not text:
        return default
    try:
        value = int(text)
    except ValueError:
        return default
    return value if value >= 0 else default


def _client_error_label(exc: Exception | None) -> str:
    if exc is None:
        return "client_error"
    if isinstance(exc, RuntimeError) and str(exc).startswith("client_error"):
        return str(exc)
    if isinstance(exc, HTTPError):
        return f"client_error:http_{exc.code}"
    if _is_timeout(exc):
        return "client_error:timeout"
    if isinstance(exc, URLError):
        return "client_error:network"
    if isinstance(exc, json.JSONDecodeError):
        return "client_error:invalid_response"
    return "client_error"


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, HTTPError):
        return exc.code in _RETRY_STATUS
    if isinstance(exc, (URLError, TimeoutError, json.JSONDecodeError)):
        return True
    if isinstance(exc, RuntimeError) and str(exc) == "client_error:invalid_response":
        return True
    return False


def _is_timeout(exc: BaseException) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, URLError):
        reason = exc.reason
        if isinstance(reason, TimeoutError):
            return True
        blob = f"{reason} {exc}".lower()
        return "timed out" in blob or "timeout" in blob
    return False


def _backoff(exc: Exception, attempt: int) -> float:
    if isinstance(exc, HTTPError):
        header = _retry_after_seconds(exc)
        if header is not None:
            return header
    return min(_MAX_BACKOFF, 1.0 * (2**attempt))


def _retry_after_seconds(exc: HTTPError) -> float | None:
    headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    raw = headers.get("Retry-After")
    if not raw:
        return None
    try:
        return min(float(raw), _MAX_BACKOFF)
    except (TypeError, ValueError):
        return None


def _drain_http_error(exc: HTTPError) -> None:
    try:
        exc.read()
    except Exception:
        return
