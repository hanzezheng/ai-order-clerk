from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

SpeechActType = Literal[
    "start_order",
    "add_line",
    "set_line",
    "remove_line",
    "replace_product",
    "refine_spec",
    "set_qty",
    "set_price",
    "use_old_price",
    "confirm_order",
    "cancel_order",
    "query_draft",
    "clarify",
    "unknown",
]


class SpeechAct(BaseModel):
    type: SpeechActType
    slots: dict[str, Any] = Field(default_factory=dict)
    span: str | None = None
    target_line_id: UUID | None = None
    confidence: float = 1.0


class TurnParse(BaseModel):
    utterance_id: str | None = None
    seq: int = 0
    expect_more: bool = False
    is_final: bool = True
    acts: list[SpeechAct] = Field(default_factory=list)
    raw_text: str = ""
