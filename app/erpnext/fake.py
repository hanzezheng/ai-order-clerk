from __future__ import annotations

from uuid import UUID

from app.erpnext.correlation import InMemoryCorrelationStore
from app.erpnext.ports import (
    CUSTOMER_DOCTYPE,
    ITEM_DOCTYPE,
    SALES_ORDER_DOCTYPE,
    ErpCustomerDraft,
    ErpGatewayError,
    ErpItemDraft,
    ErpSalesOrderDraft,
    customer_erp_name,
    item_code_for,
    sales_order_name_for,
)


class FakeErpGateway:
    """CI 夹具。记录 Customer / Item / Draft SO，不连真站、不 submit。"""

    def __init__(self, *, maps: InMemoryCorrelationStore | None = None) -> None:
        self.maps = maps or InMemoryCorrelationStore()
        self.customers: list[dict] = []
        self.items: list[dict] = []
        self.sales_orders: list[dict] = []
        self.fail_next = False
        self.fail_next_read = False
        self.calls: list[str] = []

    def ensure_customer(self, draft: ErpCustomerDraft) -> str:
        self.calls.append("ensure_customer")
        existing = self.maps.customer(draft.runtime_customer_id)
        if existing is not None:
            return existing
        name = customer_erp_name(draft.runtime_customer_id)
        self.customers.append(
            {
                "doctype": CUSTOMER_DOCTYPE,
                "name": name,
                "customer_name": draft.customer_name,
                "stall_no": draft.stall_no,
                "runtime_customer_id": str(draft.runtime_customer_id),
            }
        )
        self.maps.put_customer(draft.runtime_customer_id, name)
        return name

    def ensure_item(self, draft: ErpItemDraft) -> str:
        self.calls.append("ensure_item")
        existing = self.maps.item(draft.runtime_sku_id)
        if existing is not None:
            return existing
        code = item_code_for(draft.runtime_sku_id)
        self.items.append(
            {
                "doctype": ITEM_DOCTYPE,
                "item_code": code,
                "item_name": draft.item_name,
                "stock_uom": draft.stock_uom,
                "is_stock_item": 0,
                "runtime_sku_id": str(draft.runtime_sku_id),
            }
        )
        self.maps.put_item(draft.runtime_sku_id, code)
        return code

    def ensure_sales_order(
        self,
        draft: ErpSalesOrderDraft,
        *,
        customer: str,
        item_codes: dict[UUID, str],
    ) -> str:
        self.calls.append("ensure_sales_order")
        if self.fail_next:
            self.fail_next = False
            raise ErpGatewayError("erp_unavailable")
        existing = self.maps.order(draft.runtime_order_id)
        if existing is not None:
            return existing
        name = sales_order_name_for(draft.runtime_order_id)
        document = {
            "doctype": SALES_ORDER_DOCTYPE,
            "name": name,
            "customer": customer,
            "docstatus": draft.docstatus,
            "status": "Draft",
            "prices_incomplete": draft.prices_incomplete,
            "runtime_order_id": str(draft.runtime_order_id),
            "update_stock": 0,
            "items": [
                {
                    "item_code": item_codes[line.runtime_sku_id],
                    "qty": str(line.qty),
                    "uom": line.uom,
                    "rate": str(line.rate),
                    "price_tbd": line.price_tbd,
                }
                for line in draft.items
            ],
        }
        self.sales_orders.append(document)
        self.maps.put_order(draft.runtime_order_id, name)
        return name

    def fetch_sales_order(self, runtime_order_id: UUID) -> dict | None:
        self.calls.append("fetch_sales_order")
        if self.fail_next_read:
            self.fail_next_read = False
            raise ErpGatewayError("erp_unavailable")
        existing = self.maps.order(runtime_order_id)
        for document in self.sales_orders:
            if document.get("runtime_order_id") == str(runtime_order_id) or (
                existing is not None and document.get("name") == existing
            ):
                return document
        return None

    def list_draft_sales_orders(self, runtime_customer_id: UUID) -> list[dict]:
        self.calls.append("list_draft_sales_orders")
        if self.fail_next_read:
            self.fail_next_read = False
            raise ErpGatewayError("erp_unavailable")
        customer = self.maps.customer(runtime_customer_id)
        if customer is None:
            return []
        return [
            document
            for document in self.sales_orders
            if document.get("customer") == customer and int(document.get("docstatus") or 0) == 0
        ]

