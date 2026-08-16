from __future__ import annotations

from uuid import UUID

from app.entity.events import ORDER_CONFIRMED, DomainEvent
from app.entity.session import SalesSession
from app.erpnext.mapper import ErpDraftMapper
from app.erpnext.ports import ERPNEXT_ADAPTER_CONSUMER, ErpGateway, ErpGatewayError
from app.events.dispatcher import EventConsumer
from app.services.ports import CatalogRepository, ProcessedEventRepository


class ErpnextConsumer(EventConsumer):
    """只消费 Outbox 的 order.confirmed。ERP 失败不 mark、不抛给 Runtime。"""

    name = ERPNEXT_ADAPTER_CONSUMER
    event_types = (ORDER_CONFIRMED,)

    def __init__(
        self,
        *,
        gateway: ErpGateway,
        catalog: CatalogRepository,
        processed: ProcessedEventRepository,
    ) -> None:
        self._gateway = gateway
        self._mapper = ErpDraftMapper(catalog)
        self._processed = processed
        self.last_error: str | None = None

    def consume(self, session: SalesSession | None, event: DomainEvent) -> None:
        if self._processed.has(self.name, event.event_id):
            return
        if event.event_type != ORDER_CONFIRMED:
            return
        if session is None:
            return
        if session.draft.status != "confirmed":
            self._processed.mark(self.name, event.event_id)
            return
        customer_draft = self._mapper.customer(session)
        order_draft = self._mapper.sales_order(session)
        item_drafts = self._mapper.items(session)
        if customer_draft is None or order_draft is None or not item_drafts:
            return
        try:
            customer = self._gateway.ensure_customer(customer_draft)
            item_codes: dict[UUID, str] = {}
            for item in item_drafts:
                item_codes[item.runtime_sku_id] = self._gateway.ensure_item(item)
            self._gateway.ensure_sales_order(order_draft, customer=customer, item_codes=item_codes)
        except ErpGatewayError as exc:
            self.last_error = str(exc)
            return
        self.last_error = None
        self._processed.mark(self.name, event.event_id)
