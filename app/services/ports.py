from __future__ import annotations

from uuid import UUID

from app.entity.catalog import CustomerProfile, CustomerRecord, ProductNode
from app.entity.intake import IntakeReceipt
from app.entity.memory import EvidenceRecord, PriceMemoryRecord
from app.entity.order import DraftOrder
from app.entity.session import SalesSession
from app.entity.timeline import TimelineEvent
from app.entity.workbench import WorkbenchShift

MEMORY_EXTRACTOR_CONSUMER = "memory_extractor"
TIMELINE_CONSUMER = "timeline"


class CatalogRepository:
    def list_customers(self) -> list[CustomerRecord]:
        raise NotImplementedError

    def get_customer(self, customer_id: UUID) -> CustomerRecord | None:
        raise NotImplementedError

    def get_profile(self, customer_id: UUID) -> CustomerProfile | None:
        raise NotImplementedError

    def list_nodes(self) -> list[ProductNode]:
        raise NotImplementedError

    def get_node(self, node_id: UUID) -> ProductNode | None:
        raise NotImplementedError

    def put_customer(self, customer: CustomerRecord, profile: CustomerProfile) -> None:
        raise NotImplementedError

    def put_product_default(self, customer_id: UUID, node_id: UUID, sku_id: UUID) -> None:
        raise NotImplementedError


class AliasRepository:
    def put(self, alias: str, node_id: UUID) -> None:
        raise NotImplementedError

    def get(self, alias: str) -> UUID | None:
        raise NotImplementedError

    def snapshot(self) -> list[tuple[str, UUID]]:
        raise NotImplementedError


class PriceMemoryRepository:
    def put(self, record: PriceMemoryRecord) -> None:
        raise NotImplementedError

    def snapshot(self) -> list[PriceMemoryRecord]:
        raise NotImplementedError


class EvidenceRepository:
    def get(
        self,
        *,
        customer_id: UUID,
        kind: str,
        node_id: UUID,
        sku_id: UUID,
    ) -> EvidenceRecord | None:
        raise NotImplementedError

    def put(self, record: EvidenceRecord) -> None:
        raise NotImplementedError


class TimelineRepository:
    def list(self, session_id: UUID) -> list[TimelineEvent]:
        raise NotImplementedError

    def append(self, event: TimelineEvent) -> TimelineEvent:
        raise NotImplementedError


class ProcessedEventRepository:
    def has(self, consumer: str, event_id: UUID) -> bool:
        raise NotImplementedError

    def mark(self, consumer: str, event_id: UUID) -> None:
        raise NotImplementedError


class WorkbenchRepository:
    def get_shift(self) -> WorkbenchShift:
        raise NotImplementedError

    def save_shift(self, shift: WorkbenchShift) -> None:
        raise NotImplementedError


class IntakeReceiptRepository:
    def get(self, session_id: UUID, utterance_id: str) -> IntakeReceipt | None:
        raise NotImplementedError

    def put(self, receipt: IntakeReceipt) -> None:
        raise NotImplementedError

    def last_seq(self, session_id: UUID) -> int | None:
        raise NotImplementedError

    def set_last_seq(self, session_id: UUID, seq: int) -> None:
        raise NotImplementedError


class SessionRepository:
    def get(self, session_id: UUID) -> SalesSession | None:
        raise NotImplementedError

    def save(self, session: SalesSession) -> None:
        raise NotImplementedError


class OrderRepository:
    def save_draft(self, draft: DraftOrder) -> None:
        raise NotImplementedError

    def get_draft(self, order_id: UUID) -> DraftOrder | None:
        raise NotImplementedError
