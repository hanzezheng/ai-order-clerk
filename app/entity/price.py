from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

PriceSource = Literal["explicit", "last_deal", "last_quote", "customer_special", "market_today", "tbd"]


class PriceQuote(BaseModel):
    unit_price: Decimal | None = None
    price_uom: str | None = None
    source: PriceSource = "tbd"
    confidence: float = 1.0
