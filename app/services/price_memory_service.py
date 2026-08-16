from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.entity.memory import PriceMemoryRecord, PriceMemoryType
from app.entity.price import PriceQuote
from app.services.ports import PriceMemoryRepository


@dataclass(frozen=True)
class PriceLookup:
    record: PriceMemoryRecord | None
    expired: bool
    silent_fill_forbidden: bool = True


@dataclass(frozen=True)
class PriceMemoryService:
    """只查询。静默套 last_deal / 过期价由调用方禁止。"""

    prices: PriceMemoryRepository

    def lookup(
        self,
        *,
        customer_id,
        product_id,
        now: datetime | None = None,
        price_type: PriceMemoryType | None = None,
    ) -> PriceLookup:
        now = now or datetime.now(UTC)
        matches = [
            rec
            for rec in self.prices.snapshot()
            if rec.product_id == product_id
            and (customer_id is None or rec.customer_id in {None, customer_id})
            and (price_type is None or rec.price_type == price_type)
        ]
        if not matches:
            return PriceLookup(record=None, expired=False)
        rec = matches[-1]
        expired = rec.valid_until is not None and rec.valid_until <= now
        return PriceLookup(record=rec, expired=expired, silent_fill_forbidden=True)

    def silent_quote(self, lookup: PriceLookup) -> PriceQuote | None:
        """POC 默认不允许静默回填任何长期价格。"""
        if lookup.record is None or lookup.expired or lookup.silent_fill_forbidden:
            return None
        if lookup.record.price_type in {"last_deal", "market_today"}:
            return None
        return None
