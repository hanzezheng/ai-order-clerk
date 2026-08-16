from __future__ import annotations

from dataclasses import dataclass

from app.services.ports import (
    AliasRepository,
    CatalogRepository,
    EvidenceRepository,
    IntakeReceiptRepository,
    OrderRepository,
    OutboxRepository,
    PriceMemoryRepository,
    ProcessedEventRepository,
    SessionRepository,
    TimelineRepository,
    WorkbenchRepository,
)


@dataclass
class PersistenceBundle:
    catalog: CatalogRepository
    aliases: AliasRepository
    prices: PriceMemoryRepository
    sessions: SessionRepository
    orders: OrderRepository
    evidence: EvidenceRepository
    timeline: TimelineRepository
    processed: ProcessedEventRepository
    workbench: WorkbenchRepository
    receipts: IntakeReceiptRepository
    outbox: OutboxRepository
