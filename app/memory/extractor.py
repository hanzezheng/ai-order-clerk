from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.entity.events import ORDER_CONFIRMED, DomainEvent
from app.entity.memory import MemoryCandidate, PriceMemoryRecord
from app.entity.session import SalesSession
from app.entity.speech import SpeechAct
from app.memory.evidence import EvidenceStore
from app.services.catalog_service import OntologyService


class MemoryExtractor:
    """只从确认后的领域事件抽出候选。禁止读用户原话。"""

    def __init__(
        self,
        *,
        evidence: EvidenceStore | None = None,
        ontology: OntologyService | None = None,
    ) -> None:
        self._evidence = evidence or EvidenceStore()
        self._ontology = ontology
        self._seen: set[UUID] = set()

    def extract(self, act: SpeechAct, session: SalesSession) -> list[MemoryCandidate]:
        """旧入口：SpeechAct 不得写长期记忆。"""
        return []

    def extract_from_events(self, session: SalesSession, events: list[DomainEvent]) -> list[MemoryCandidate]:
        out: list[MemoryCandidate] = []
        order_id = session.draft.order_id
        for event in events:
            if event.event_id in self._seen:
                continue
            if event.event_type != ORDER_CONFIRMED:
                continue
            if event.aggregate_id != order_id:
                continue
            self._seen.add(event.event_id)
            out.extend(self._from_confirmed_draft(session))
        return out

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
