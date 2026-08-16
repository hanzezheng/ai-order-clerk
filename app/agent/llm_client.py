from __future__ import annotations

from typing import Any, Protocol


class LlmClient(Protocol):
    def complete(self, *, system: str, user: str) -> Any: ...


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

    def complete(self, *, system: str, user: str) -> Any:
        if self._error is not None:
            raise self._error
        if user in self._responses:
            return self._responses[user]
        if self._default is not None:
            return self._default
        raise LookupError(f"no fake LLM payload for {user!r}")
