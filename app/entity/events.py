from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

ORDER_STARTED = "order.started"
ORDER_LINE_UPSERTED = "order.line_upserted"
ORDER_LINE_REMOVED = "order.line_removed"
ORDER_CONFIRMED = "order.confirmed"
ORDER_CANCELLED = "order.cancelled"
ORDER_PRICE_FILLED = "order.price_filled"
PREFERENCE_ADJUSTED = "memory.preference_adjusted"


class DomainEvent(BaseModel):
    event_type: str
    aggregate_id: UUID
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    event_id: UUID = Field(default_factory=uuid4)


class OutboxRecord(BaseModel):
    """可靠事实信封。不是投递状态机。"""

    event_id: UUID
    event_type: str
    aggregate_type: str
    aggregate_id: UUID
    session_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_event(self) -> DomainEvent:
        return DomainEvent(
            event_id=self.event_id,
            event_type=self.event_type,
            aggregate_id=self.aggregate_id,
            payload=dict(self.payload),
            occurred_at=self.occurred_at,
        )


def aggregate_type_for(event_type: str) -> str:
    if event_type.startswith("memory."):
        return "memory"
    return "order"


class DomainEventPublisher(Protocol):
    """销售内核只发布；库存/付款/采购消费者阶段 2 再接。"""

    def publish(self, event: DomainEvent) -> None: ...


class NullEventPublisher:
    def publish(self, event: DomainEvent) -> None:
        return None


class RecordingEventPublisher:
    """测试探针：记录本回合事件，不得作为 Memory/Timeline 消费来源。"""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)
