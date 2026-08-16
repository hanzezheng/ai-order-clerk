from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.entity.memory import MemoryStatus

PRODUCT_DEFAULT_THRESHOLD = 3


class EvidenceRecord(BaseModel):
    customer_id: UUID
    kind: str
    node_id: UUID
    sku_id: UUID
    count: int = 0
    positive_count: int = 0
    negative_count: int = 0
    status: MemoryStatus = "pending"
    last_confirmed_at: datetime | None = None


class EvidenceStore:
    """确认偏好的证据累计。净 count 由正负计数得出；本阶段不做衰减。"""

    def __init__(self) -> None:
        self._items: dict[tuple[UUID, str, UUID, UUID], EvidenceRecord] = {}

    def observe(
        self,
        *,
        customer_id: UUID,
        kind: str,
        node_id: UUID,
        sku_id: UUID,
        at: datetime | None = None,
    ) -> EvidenceRecord:
        return self.adjust(
            customer_id=customer_id,
            kind=kind,
            node_id=node_id,
            sku_id=sku_id,
            delta=1,
            at=at,
        )

    def adjust(
        self,
        *,
        customer_id: UUID,
        kind: str,
        node_id: UUID,
        sku_id: UUID,
        delta: int,
        at: datetime | None = None,
    ) -> EvidenceRecord:
        key = (customer_id, kind, node_id, sku_id)
        now = at or datetime.now(UTC)
        current = self._items.get(key)
        if current is None:
            current = EvidenceRecord(
                customer_id=customer_id,
                kind=kind,
                node_id=node_id,
                sku_id=sku_id,
            )
        positive = current.positive_count
        negative = current.negative_count
        update: dict[str, object] = {}
        if delta > 0:
            positive += delta
            update["last_confirmed_at"] = now
        elif delta < 0:
            negative += -delta
        count = max(0, positive - negative)
        status: MemoryStatus = "active" if count >= PRODUCT_DEFAULT_THRESHOLD else "pending"
        update.update(
            {
                "positive_count": positive,
                "negative_count": negative,
                "count": count,
                "status": status,
            }
        )
        updated = current.model_copy(update=update)
        self._items[key] = updated
        return updated

    def get(
        self,
        *,
        customer_id: UUID,
        kind: str,
        node_id: UUID,
        sku_id: UUID,
    ) -> EvidenceRecord | None:
        return self._items.get((customer_id, kind, node_id, sku_id))
