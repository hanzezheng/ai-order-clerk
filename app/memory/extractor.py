from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.entity.memory import MemoryCandidate, PriceMemoryRecord
from app.entity.session import SalesSession
from app.entity.speech import SpeechAct


class MemoryExtractor:
    """从已执行的 SpeechAct 产出候选。默认空；确认单本身不产出。"""

    def extract(self, act: SpeechAct, session: SalesSession) -> list[MemoryCandidate]:
        if act.type == "confirm_order":
            return []
        customer = session.draft.customer
        if customer is None or customer.id is None:
            return []
        if act.type != "set_price":
            return []
        line = None
        if session.focus_line_id:
            line = next((ln for ln in session.draft.lines if ln.line_id == session.focus_line_id), None)
        if line is None and session.draft.lines:
            line = session.draft.lines[-1]
        if line is None or line.product_sku_id is None:
            return []
        if line.price.source != "explicit" or line.price.unit_price is None:
            return []
        now = datetime.now(UTC)
        return [
            MemoryCandidate(
                kind="price",
                confidence=1.0,
                reason="explicit_set_price",
                source_act=act.type,
                price=PriceMemoryRecord(
                    price_type="last_quote",
                    customer_id=customer.id,
                    product_id=line.product_sku_id,
                    unit_price=line.price.unit_price,
                    price_uom=line.price.price_uom or "块",
                    valid_until=now + timedelta(hours=24),
                    valid_from=now,
                ),
            )
        ]
