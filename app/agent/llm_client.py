from __future__ import annotations

import json
from os import environ
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float = 20.0) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def available(self) -> bool:
        return True

    def complete(self, *, system: str, user: str) -> Any:
        url = self._base_url + "/chat/completions"
        payload = {
            "model": self._model,
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
        try:
            with urlopen(request, timeout=self._timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("client_error") from exc
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("client_error") from exc


def client_from_env() -> LlmClient:
    api_key = (environ.get("LLM_API_KEY") or "").strip()
    if not api_key:
        return UnconfiguredLlmClient()
    base_url = (environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").strip()
    model = (environ.get("LLM_MODEL") or "gpt-4o-mini").strip()
    return HttpLlmClient(api_key=api_key, base_url=base_url, model=model)
