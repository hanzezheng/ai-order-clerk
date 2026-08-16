from __future__ import annotations

from app.agent.llm_schema import LlmTurnParse
from app.entity.speech import SpeechAct, SpeechActType, TurnParse

_FORBIDDEN_SLOT_KEYS = {
    "sku_id",
    "product_id",
    "customer_id",
    "node_id",
    "line_id",
    "target_line_id",
}


def _slot_value(key: str, value: object) -> object:
    if key in {"qty", "unit_price"} and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def llm_turn_to_domain(llm: LlmTurnParse, *, raw_text: str) -> TurnParse:
    """LLM Output Schema → 领域 SpeechAct / TurnParse。spec_mention 原样保留，不映射 SKU。"""
    acts: list[SpeechAct] = []
    for item in llm.acts:
        slots = {
            key: _slot_value(key, value)
            for key, value in item.slots.model_dump(exclude_none=True).items()
            if key not in _FORBIDDEN_SLOT_KEYS
        }
        act_type: SpeechActType = item.type
        acts.append(SpeechAct(type=act_type, slots=slots, span=item.span))
    return TurnParse(
        raw_text=raw_text,
        acts=acts,
        is_final=True,
        parser_name="llm",
        fallback=False,
        fallback_reason=None,
    )
