from __future__ import annotations

from dataclasses import dataclass

from app.entity.events import ORDER_CONFIRMED, PREFERENCE_ADJUSTED
from app.entity.memory import MemoryCandidate
from app.memory.evidence import PRODUCT_DEFAULT_THRESHOLD


@dataclass(frozen=True)
class MemoryDecision:
    write: bool
    reason: str


class MemoryPolicy:
    """长期记忆闸门。只审核确认事件候选；LLM 不得调用本闸门改结论。"""

    def decide(self, candidate: MemoryCandidate) -> MemoryDecision:
        if candidate.source_event == PREFERENCE_ADJUSTED:
            return MemoryDecision(False, "preference_adjusted_does_not_write_default")
        if candidate.source_event != ORDER_CONFIRMED:
            return MemoryDecision(False, "memory_only_from_confirm_event")
        if candidate.kind == "product_default":
            if candidate.customer_id is None or candidate.node_id is None or candidate.sku_id is None:
                return MemoryDecision(False, "product_default_incomplete")
            if candidate.evidence_count < PRODUCT_DEFAULT_THRESHOLD:
                return MemoryDecision(False, "evidence_below_threshold")
            return MemoryDecision(True, "product_default_threshold_met")
        if candidate.kind == "price" and candidate.price is not None:
            price = candidate.price
            if price.customer_id is None:
                return MemoryDecision(False, "unbound_customer")
            if price.price_type != "last_deal":
                return MemoryDecision(False, "price_type_not_writable")
            return MemoryDecision(True, "last_deal_from_confirm")
        return MemoryDecision(False, "unknown_candidate")
