from __future__ import annotations

from uuid import UUID

from app.erpnext.facts import OrderPostingFact
from app.erpnext.ports import ErpGatewayError, ErpReadGateway


class ErpnextReadAdapter:
    """只读 Adapter。ERP 失败变成 unavailable，不抛给 Runtime。"""

    def __init__(self, gateway: ErpReadGateway) -> None:
        self._gateway = gateway

    def posting_for(self, runtime_order_id: UUID) -> OrderPostingFact:
        try:
            document = self._gateway.fetch_sales_order(runtime_order_id)
        except ErpGatewayError:
            return OrderPostingFact(runtime_order_id=runtime_order_id, posting="unavailable")
        if not document:
            return OrderPostingFact(runtime_order_id=runtime_order_id, posting="pending")
        items = document.get("items") if isinstance(document.get("items"), list) else []
        incomplete = document.get("prices_incomplete")
        return OrderPostingFact(
            runtime_order_id=runtime_order_id,
            posting="posted",
            prices_incomplete=bool(incomplete) if incomplete is not None else None,
            line_count=len(items),
        )

    def open_draft_count(self, runtime_customer_id: UUID) -> int | None:
        try:
            documents = self._gateway.list_draft_sales_orders(runtime_customer_id)
        except ErpGatewayError:
            return None
        return len(documents)

