from __future__ import annotations

from dataclasses import dataclass

from app.entity.memory import MemoryCandidate


@dataclass(frozen=True)
class MemoryDecision:
    write: bool
    reason: str


class MemoryPolicy:
    """长期记忆闸门。订单确认、临时规格、数量一律不写。"""

    def decide(self, candidate: MemoryCandidate) -> MemoryDecision:
        if candidate.source_act == "confirm_order":
            return MemoryDecision(False, "order_confirm_does_not_write_memory")
        if candidate.kind == "product_default":
            return MemoryDecision(False, "temp_spec_does_not_write_profile")
        if candidate.kind == "product_alias":
            alias = candidate.alias
            if alias is None or candidate.confidence < 0.8:
                return MemoryDecision(False, "alias_confidence_too_low")
            return MemoryDecision(True, "alias_ok")
        if candidate.kind == "price" and candidate.price is not None:
            price = candidate.price
            if price.customer_id is None:
                return MemoryDecision(False, "unbound_customer")
            if price.price_type != "last_quote":
                return MemoryDecision(False, "price_type_not_writable")
            if candidate.source_act != "set_price":
                return MemoryDecision(False, "price_only_from_set_price")
            return MemoryDecision(True, "price_quote_ok")
        return MemoryDecision(False, "unknown_candidate")
