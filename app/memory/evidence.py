from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.entity.memory import EvidenceRecord, MemoryStatus
from app.services.ports import EvidenceRepository

PRODUCT_DEFAULT_THRESHOLD = 3


class EvidenceStore:
    """确认偏好的证据累计。净 count 由正负计数得出；本阶段不做衰减。"""

    def __init__(self, repo: EvidenceRepository) -> None:
        self._repo = repo

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
        """delta 调整工作净 count；正负计数只追加历史，无正向时的负向不欠未来的债。"""
        now = at or datetime.now(UTC)
        current = self._repo.get(
            customer_id=customer_id,
            kind=kind,
            node_id=node_id,
            sku_id=sku_id,
        )
        if current is None:
            current = EvidenceRecord(
                customer_id=customer_id,
                kind=kind,
                node_id=node_id,
                sku_id=sku_id,
            )
        positive = current.positive_count
        negative = current.negative_count
        count = current.count
        update: dict[str, object] = {}
        if delta > 0:
            positive += delta
            count += delta
            update["last_confirmed_at"] = now
        elif delta < 0:
            negative += -delta
            count = max(0, count + delta)
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
        self._repo.put(updated)
        return updated

    def get(
        self,
        *,
        customer_id: UUID,
        kind: str,
        node_id: UUID,
        sku_id: UUID,
    ) -> EvidenceRecord | None:
        return self._repo.get(
            customer_id=customer_id,
            kind=kind,
            node_id=node_id,
            sku_id=sku_id,
        )
