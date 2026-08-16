from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.entity.session import SalesSession
from app.erpnext.ports import ErpCustomerDraft, ErpItemDraft, ErpSalesOrderDraft, ErpSalesOrderLine
from app.services.ports import CatalogRepository


class ErpDraftMapper:
    """Runtime 已确认快照 → Adapter 草稿。不写 Catalog，不改价。"""

    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    def customer(self, session: SalesSession) -> ErpCustomerDraft | None:
        ref = session.draft.customer
        if ref is None or ref.id is None:
            return None
        record = self._catalog.get_customer(ref.id)
        name = record.display_name if record is not None else ref.name
        stall = record.stall_no if record is not None else ref.stall_no
        return ErpCustomerDraft(runtime_customer_id=ref.id, customer_name=name, stall_no=stall)

    def items(self, session: SalesSession) -> list[ErpItemDraft]:
        out: list[ErpItemDraft] = []
        seen: set[UUID] = set()
        for line in session.draft.lines:
            sku_id = line.product_sku_id
            if sku_id is None or sku_id in seen:
                continue
            node = self._catalog.get_node(sku_id)
            if node is None or node.level != "sku":
                continue
            seen.add(sku_id)
            out.append(ErpItemDraft(runtime_sku_id=sku_id, item_name=node.name, stock_uom=node.default_uom or line.qty.uom))
        return out

    def sales_order(self, session: SalesSession) -> ErpSalesOrderDraft | None:
        customer = session.draft.customer
        if customer is None or customer.id is None:
            return None
        lines: list[ErpSalesOrderLine] = []
        for line in session.draft.lines:
            if line.product_sku_id is None:
                continue
            tbd = line.price.source != "explicit" or line.price.unit_price is None
            rate = Decimal("0") if tbd else line.price.unit_price
            lines.append(
                ErpSalesOrderLine(
                    runtime_sku_id=line.product_sku_id,
                    qty=line.qty.value,
                    uom=line.qty.uom,
                    rate=rate,
                    price_tbd=tbd,
                )
            )
        if not lines:
            return None
        incomplete = any(item.price_tbd for item in lines) or any(
            ln.price.source == "tbd" for ln in session.draft.lines
        )
        return ErpSalesOrderDraft(
            runtime_order_id=session.draft.order_id,
            runtime_customer_id=customer.id,
            prices_incomplete=incomplete,
            items=tuple(lines),
            docstatus=0,
        )
