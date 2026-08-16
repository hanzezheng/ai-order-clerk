from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.entity.events import ORDER_CONFIRMED, PREFERENCE_ADJUSTED, DomainEvent
from app.entity.memory import MemoryCandidate, PriceMemoryRecord
from app.entity.session import SalesSession
from app.entity.speech import SpeechAct
from app.memory.evidence import EvidenceStore
from app.services.catalog_service import OntologyService
from app.services.ports import MEMORY_EXTRACTOR_CONSUMER, ProcessedEventRepository


class MemoryExtractor:
    """只从确认后的领域事件抽出候选。禁止读用户原话。"""

    def __init__(
        self,
        *,
        evidence: EvidenceStore,
        processed: ProcessedEventRepository,
        ontology: OntologyService | None = None,
    ) -> None:
        self._evidence = evidence
        self._processed = processed
        self._ontology = ontology

    def extract(self, act: SpeechAct, session: SalesSession) -> list[MemoryCandidate]:
        """旧入口：SpeechAct 不得写长期记忆。"""
        return []

    def extract_from_events(self, session: SalesSession, events: list[DomainEvent]) -> list[MemoryCandidate]:
        out: list[MemoryCandidate] = []
        order_id = session.draft.order_id
        confirmed: list[DomainEvent] = []
        adjusted: list[DomainEvent] = []
        for event in events:
            if self._processed.has(MEMORY_EXTRACTOR_CONSUMER, event.event_id):
                continue
            if event.aggregate_id != order_id:
                continue
            if event.event_type == ORDER_CONFIRMED:
                confirmed.append(event)
            elif event.event_type == PREFERENCE_ADJUSTED:
                adjusted.append(event)
        for event in confirmed:
            self._processed.mark(MEMORY_EXTRACTOR_CONSUMER, event.event_id)
            out.extend(self._from_confirmed_draft(session))
        for event in adjusted:
            self._processed.mark(MEMORY_EXTRACTOR_CONSUMER, event.event_id)
            out.extend(self._from_preference_adjusted(event))
        return out

    def _from_preference_adjusted(self, event: DomainEvent) -> list[MemoryCandidate]:
        payload = event.payload or {}
        customer_id = _as_uuid(payload.get("customer_id"))
        node_id = _as_uuid(payload.get("node_id"))
        from_sku_id = _as_uuid(payload.get("from_sku_id"))
        if customer_id is None or node_id is None or from_sku_id is None:
            return []
        evidence = self._evidence.adjust(
            customer_id=customer_id,
            kind="product_default",
            node_id=node_id,
            sku_id=from_sku_id,
            delta=-1,
        )
        return [
            MemoryCandidate(
                kind="product_default",
                confidence=1.0,
                reason="preference_adjusted_negative_evidence",
                source_event=PREFERENCE_ADJUSTED,
                customer_id=customer_id,
                node_id=node_id,
                sku_id=from_sku_id,
                evidence_count=evidence.count,
                status=evidence.status,
            )
        ]

    def _from_confirmed_draft(self, session: SalesSession) -> list[MemoryCandidate]:
        customer = session.draft.customer
        if customer is None or customer.id is None:
            return []
        if session.draft.status != "confirmed":
            return []
        now = datetime.now(UTC)
        found: list[MemoryCandidate] = []
        for line in session.draft.lines:
            if line.product_sku_id is None:
                continue
            node_id = self._preference_node_id(line)
            if node_id is not None:
                evidence = self._evidence.observe(
                    customer_id=customer.id,
                    kind="product_default",
                    node_id=node_id,
                    sku_id=line.product_sku_id,
                    at=now,
                )
                found.append(
                    MemoryCandidate(
                        kind="product_default",
                        confidence=1.0,
                        reason="confirmed_sku_preference",
                        source_event=ORDER_CONFIRMED,
                        customer_id=customer.id,
                        node_id=node_id,
                        sku_id=line.product_sku_id,
                        evidence_count=evidence.count,
                        status=evidence.status,
                        last_confirmed_at=now,
                    )
                )
            if line.price.source != "explicit" or line.price.unit_price is None:
                continue
            found.append(
                MemoryCandidate(
                    kind="price",
                    confidence=1.0,
                    reason="confirmed_explicit_price",
                    source_event=ORDER_CONFIRMED,
                    customer_id=customer.id,
                    sku_id=line.product_sku_id,
                    status="active",
                    last_confirmed_at=now,
                    price=PriceMemoryRecord(
                        price_type="last_deal",
                        customer_id=customer.id,
                        product_id=line.product_sku_id,
                        unit_price=line.price.unit_price,
                        price_uom=line.price.price_uom or "块",
                        valid_until=now + timedelta(days=7),
                        valid_from=now,
                        status="active",
                        last_confirmed_at=now,
                    ),
                )
            )
        return found

    def _preference_node_id(self, line) -> UUID | None:
        node = line.mention.resolved_sku or line.mention.matched_node
        if node is None:
            return line.matched_node_id
        if self._ontology is not None:
            variety = self._ontology.variety_id(node)
            if variety is not None:
                return variety
        if line.mention.matched_node is not None:
            return line.mention.matched_node.id
        return line.matched_node_id


def _as_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
