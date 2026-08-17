from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LlmActType = Literal[
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


class LlmActSlots(BaseModel):
    """LLM 语言槽。禁止 sku_id / customer_id / line_id / SKU 全称。
    spec_mention 只是口语规格。replacement_mention 只是替品原词，禁止映射 SKU。
    """

    model_config = ConfigDict(extra="forbid")

    customer_mention: str | None = None
    product_mention: str | None = None
    replacement_mention: str | None = None
    spec_mention: str | None = None
    qty: int | float | None = None
    uom: str | None = None
    unit_price: int | float | None = None
    price_uom: str | None = None
    mode: str | None = None
    mention: str | None = None


class LlmSpeechAct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: LlmActType
    slots: LlmActSlots = Field(default_factory=LlmActSlots)
    span: str | None = None


class LlmTurnParse(BaseModel):
    """LLM 输出契约，不是领域 TurnParse。"""

    model_config = ConfigDict(extra="forbid")

    acts: list[LlmSpeechAct] = Field(default_factory=list)
