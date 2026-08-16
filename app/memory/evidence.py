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
    status: MemoryStatus = "pending"
    last_confirmed_at: datetime | None = None


class EvidenceStore:
    """确认偏好的证据累计。不是模型打分，本阶段不做衰减。"""

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
        count = current.count + 1
        status: MemoryStatus = "active" if count >= PRODUCT_DEFAULT_THRESHOLD else "pending"
        updated = current.model_copy(
            update={"count": count, "status": status, "last_confirmed_at": now}
        )
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
