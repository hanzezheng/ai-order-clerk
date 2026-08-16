from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.agent.llm_client import LlmClient
from app.agent.llm_convert import llm_turn_to_domain
from app.agent.llm_schema import LlmTurnParse
from app.agent.parser import TurnParser
from app.agent.prompts import PARSER_SYSTEM_PROMPT
from app.agent.turn_parser import RuleTurnParser
from app.entity.speech import TurnParse

_ADAPTER = TypeAdapter(LlmTurnParse)


class LlmParseError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def parse_llm_output(raw: Any) -> LlmTurnParse:
    if isinstance(raw, (str, bytes, bytearray)):
        return _ADAPTER.validate_json(raw)
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
    """自然语言 → TurnParse。失败则 fallback 到 RuleTurnParser。"""

    def __init__(self, client: LlmClient, fallback: TurnParser | None = None) -> None:
        self._client = client
        self._fallback = fallback or RuleTurnParser()

    def parse(self, text: str) -> TurnParse:
        try:
            raw = self._client.complete(system=PARSER_SYSTEM_PROMPT, user=text)
            llm_out = parse_llm_output(raw)
            if not llm_out.acts and text.strip():
                raise LlmParseError("empty_acts")
            return llm_turn_to_domain(llm_out, raw_text=text)
        except Exception as exc:
            return self._fallback_parse(text, _fallback_reason(exc))

    def _fallback_parse(self, text: str, reason: str) -> TurnParse:
        parsed = self._fallback.parse(text)
        return parsed.model_copy(
            update={
                "parser_name": "rule",
                "fallback": True,
                "fallback_reason": reason,
            }
        )
