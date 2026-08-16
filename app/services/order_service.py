from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.entity.catalog import CustomerRef, ProductMention, ProductNode
from app.entity.events import (
    ORDER_CONFIRMED,
    ORDER_LINE_REMOVED,
    ORDER_LINE_UPSERTED,
    ORDER_STARTED,
    DomainEvent,
    DomainEventPublisher,
    NullEventPublisher,
)
from app.entity.order import DraftOrder, OrderLine, Quantity
from app.entity.price import PriceQuote
from app.entity.session import SalesSession
from app.services.catalog_service import OntologyService
from app.services.ports import OrderRepository


class OrderService:
    def __init__(
        self,
        orders: OrderRepository,
        ontology: OntologyService,
        events: DomainEventPublisher | None = None,
    ) -> None:
        self._orders = orders
        self._ontology = ontology
        self._events = events or NullEventPublisher()

    def start_draft(self, session: SalesSession, customer: CustomerRef) -> DraftOrder:
        session.draft.customer = customer
        session.draft.status = "draft"
        session.status = "drafting"
        session.pending_customer_candidates = []
        self._orders.save_draft(session.draft)
        self._events.publish(
            DomainEvent(
                event_type=ORDER_STARTED,
                aggregate_id=session.draft.order_id,
                payload={"customer_id": str(customer.id), "session_id": str(session.session_id)},
            )
        )
        return session.draft

    def apply_line(
        self,
        session: SalesSession,
        mention: ProductMention,
        qty: Quantity,
        op: str,
    ) -> OrderLine:
        existing = self._find_line(session, mention)
        if existing is None:
            line = OrderLine(
                mention=mention,
                product_sku_id=mention.resolved_sku.id if mention.resolved_sku else None,
                matched_node_id=mention.matched_node.id if mention.matched_node else None,
                qty=qty,
                merge_op=op,
                price=PriceQuote(source="tbd"),
                line_status=self._status(mention),
            )
            session.draft.lines.append(line)
            existing = line
        else:
            if op == "add":
                existing.qty = Quantity(value=existing.qty.value + qty.value, uom=qty.uom or existing.qty.uom)
            elif op == "remove":
                session.draft.lines = [ln for ln in session.draft.lines if ln.line_id != existing.line_id]
                self._orders.save_draft(session.draft)
                self._events.publish(
                    DomainEvent(
                        event_type=ORDER_LINE_REMOVED,
                        aggregate_id=session.draft.order_id,
                        payload={"line_id": str(existing.line_id)},
                    )
                )
                session.focus_line_id = session.draft.lines[-1].line_id if session.draft.lines else None
                return existing
            else:
                existing.qty = Quantity(value=qty.value, uom=qty.uom or existing.qty.uom)
            self._upgrade_mention(existing, mention)
            existing.merge_op = op
            existing.line_status = self._status(existing.mention)
        session.focus_line_id = existing.line_id
        self._orders.save_draft(session.draft)
        self._events.publish(
            DomainEvent(
                event_type=ORDER_LINE_UPSERTED,
                aggregate_id=session.draft.order_id,
                payload={
                    "line_id": str(existing.line_id),
                    "qty": str(existing.qty.value),
                    "uom": existing.qty.uom,
                    "sku_id": str(existing.product_sku_id) if existing.product_sku_id else None,
                },
            )
        )
        return existing

    def set_qty(self, session: SalesSession, line: OrderLine, qty: Quantity, op: str) -> OrderLine:
        if op == "add":
            line.qty = Quantity(value=line.qty.value + qty.value, uom=qty.uom or line.qty.uom)
        else:
            line.qty = Quantity(value=qty.value, uom=qty.uom or line.qty.uom)
        session.focus_line_id = line.line_id
        self._orders.save_draft(session.draft)
        self._events.publish(
            DomainEvent(
                event_type=ORDER_LINE_UPSERTED,
                aggregate_id=session.draft.order_id,
                payload={"line_id": str(line.line_id), "qty": str(line.qty.value), "op": op},
            )
        )
        return line

    def confirm(self, session: SalesSession) -> DraftOrder:
        session.draft.status = "confirmed"
        session.status = "confirmed"
        for line in session.draft.lines:
            if line.product_sku_id:
                line.line_status = "price_tbd" if line.price.source == "tbd" else "confirmed"
        self._orders.save_draft(session.draft)
        self._events.publish(
            DomainEvent(
                event_type=ORDER_CONFIRMED,
                aggregate_id=session.draft.order_id,
                payload={
                    "prices_incomplete": any(ln.price.source == "tbd" for ln in session.draft.lines),
                    "line_count": len(session.draft.lines),
                },
            )
        )
        return session.draft

    def _status(self, mention: ProductMention) -> str:
        if mention.resolved_sku:
            return "price_tbd"
        if mention.matched_node:
            return "pending_clarify"
        return "unresolved"

    def _upgrade_mention(self, line: OrderLine, mention: ProductMention) -> None:
        if mention.resolved_sku:
            line.mention = mention
            line.product_sku_id = mention.resolved_sku.id
            line.matched_node_id = mention.matched_node.id if mention.matched_node else line.matched_node_id
        elif mention.matched_node and line.mention.matched_node is None:
            line.mention = mention
            line.matched_node_id = mention.matched_node.id

    def _find_line(self, session: SalesSession, mention: ProductMention) -> OrderLine | None:
        node = mention.resolved_sku or mention.matched_node
        if node is None:
            return None
        for line in session.draft.lines:
            other_id = line.product_sku_id or line.matched_node_id
            if other_id is None:
                continue
            other = self._ontology.get(other_id)
            if other and self._ontology.related(node, other):
                return line
        return None


def quantity(value: int | Decimal, uom: str) -> Quantity:
    return Quantity(value=Decimal(value), uom=uom)
