from __future__ import annotations

from typing import Any

import json

from pydantic import TypeAdapter, ValidationError

from app.agent.llm_client import LlmClient
from app.agent.llm_convert import llm_turn_to_domain
from app.agent.llm_schema import LlmActSlots, LlmTurnParse
from app.agent.parser import TurnParser
from app.agent.prompts import PARSER_PROMPT_ID, PARSER_SYSTEM_PROMPT
from app.agent.turn_parser import RuleTurnParser
from app.entity.speech import TurnParse

_ADAPTER = TypeAdapter(LlmTurnParse)
_LANGUAGE_SLOT_KEYS = frozenset(LlmActSlots.model_fields)

# 语言层封闭同义词 → 领域 type。不是新 SpeechAct，不映射 confirm。
LLM_ACT_TYPE_ALIASES: dict[str, str] = {
    "add_item": "add_line",
    "add_product": "add_line",
    "add_goods": "add_line",
    "insert_item": "add_line",
    "set_item": "set_line",
    "update_item": "set_line",
    "update_line": "set_line",
    "create_order": "start_order",
    "open_order": "start_order",
    "new_order": "start_order",
    "delete_item": "remove_line",
    "drop_item": "remove_line",
    "delete_line": "remove_line",
    "set_spec": "refine_spec",
    "update_spec": "refine_spec",
    "specify": "refine_spec",
    "add_spec": "refine_spec",
    "old_price": "use_old_price",
}


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


def normalize_llm_shape(payload: Any) -> Any:
    """机械形状归一：根数组、语言槽位置、封闭 type 同义词。不猜 SKU / 客户，不放宽业务字段。"""
    if isinstance(payload, list):
        payload = {"acts": payload}
    if not isinstance(payload, dict):
        return payload
    acts = payload.get("acts")
    if not isinstance(acts, list):
        return payload
    normalized_acts: list[Any] = []
    for item in acts:
        if not isinstance(item, dict):
            normalized_acts.append(item)
            continue
        act = dict(item)
        raw_type = act.get("type")
        if isinstance(raw_type, str):
            mapped = LLM_ACT_TYPE_ALIASES.get(raw_type.strip().lower())
            if mapped:
                act["type"] = mapped
        slots = act.get("slots")
        lifted = dict(slots) if isinstance(slots, dict) else {}
        for key in list(act.keys()):
            if key not in _LANGUAGE_SLOT_KEYS:
                continue
            value = act.pop(key)
            if key not in lifted or lifted[key] is None:
                lifted[key] = value
        if lifted:
            act["slots"] = lifted
        elif "slots" in act and not isinstance(act.get("slots"), dict):
            act.pop("slots", None)
        normalized_acts.append(act)
    out = dict(payload)
    out["acts"] = normalized_acts
    return out


def parse_llm_output(raw: Any) -> LlmTurnParse:
    if isinstance(raw, (str, bytes, bytearray)):
        text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
        payload: Any = json.loads(_strip_fences(text))
    else:
        payload = raw
    return _ADAPTER.validate_python(normalize_llm_shape(payload))


def _fallback_reason(exc: Exception) -> str:
    if isinstance(exc, LlmParseError):
        return exc.reason
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_json"
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
