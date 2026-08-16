from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.agent.llm_client import LlmClient
from app.agent.llm_convert import llm_turn_to_domain
from app.agent.llm_schema import LlmTurnParse
from app.agent.parser import TurnParser
from app.agent.prompts import PARSER_PROMPT_ID, PARSER_SYSTEM_PROMPT
from app.agent.turn_parser import RuleTurnParser
from app.entity.speech import TurnParse

_ADAPTER = TypeAdapter(LlmTurnParse)


class LlmParseError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    return text


def parse_llm_output(raw: Any) -> LlmTurnParse:
    if isinstance(raw, (str, bytes, bytearray)):
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        return _ADAPTER.validate_json(_strip_fences(text))
    return _ADAPTER.validate_python(raw)


def _fallback_reason(exc: Exception) -> str:
    if isinstance(exc, LlmParseError):
        return exc.reason
    if isinstance(exc, ValidationError):
        kinds = {item["type"] for item in exc.errors()}
        if any("json" in kind for kind in kinds):
            return "invalid_json"
        return "schema_validation_error"
    return "client_error"


class LLMTurnParser:
    """自然语言 → TurnParse。未配置不发请求；失败则整回合规则兜底。"""

    prompt_id = PARSER_PROMPT_ID

    def __init__(self, client: LlmClient, fallback: TurnParser | None = None) -> None:
        self._client = client
        self._fallback = fallback or RuleTurnParser()

    def parse(self, text: str) -> TurnParse:
        if not self._client.available():
            return self._fallback_parse(text, "llm_unconfigured", attempted=False)
        try:
            raw = self._client.complete(system=PARSER_SYSTEM_PROMPT, user=text)
            llm_out = parse_llm_output(raw)
            if not llm_out.acts and text.strip():
                raise LlmParseError("empty_acts")
            return llm_turn_to_domain(llm_out, raw_text=text)
        except Exception as exc:
            return self._fallback_parse(text, _fallback_reason(exc), attempted=True)

    def _fallback_parse(self, text: str, reason: str, *, attempted: bool) -> TurnParse:
        parsed = self._fallback.parse(text)
        return parsed.model_copy(
            update={
                "parser_name": "rule",
                "fallback": attempted,
                "fallback_reason": reason,
            }
        )
