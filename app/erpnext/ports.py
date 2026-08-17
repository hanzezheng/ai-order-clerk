from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from uuid import UUID

ERPNEXT_ADAPTER_CONSUMER = "erpnext_adapter"

CUSTOMER_DOCTYPE = "Customer"
ITEM_DOCTYPE = "Item"
SALES_ORDER_DOCTYPE = "Sales Order"


def customer_erp_name(runtime_customer_id: UUID) -> str:
    return f"CUST-{runtime_customer_id.hex[:12].upper()}"


def item_code_for(runtime_sku_id: UUID) -> str:
    return f"SKU-{runtime_sku_id.hex[:12].upper()}"


def sales_order_name_for(runtime_order_id: UUID) -> str:
    return f"SO-{runtime_order_id.hex[:12].upper()}"


class ErpGatewayError(Exception):
    """ERP 调用失败。不得传回 Runtime 改确认结果。"""


@dataclass(frozen=True)
class ErpCustomerDraft:
    runtime_customer_id: UUID
    customer_name: str
    stall_no: str | None = None


@dataclass(frozen=True)
class ErpItemDraft:
    runtime_sku_id: UUID
    item_name: str
    stock_uom: str = "件"


@dataclass(frozen=True)
class ErpSalesOrderLine:
    runtime_sku_id: UUID
    qty: Decimal
    uom: str
    rate: Decimal
    price_tbd: bool


@dataclass(frozen=True)
class ErpSalesOrderDraft:
    runtime_order_id: UUID
    runtime_customer_id: UUID
    prices_incomplete: bool
    items: tuple[ErpSalesOrderLine, ...] = field(default_factory=tuple)
    docstatus: int = 0


class ErpGateway(Protocol):
    def ensure_customer(self, draft: ErpCustomerDraft) -> str:
        """Return ERP Customer name. Idempotent on runtime_customer_id."""

    def ensure_item(self, draft: ErpItemDraft) -> str:
        """Return item_code. Idempotent on runtime_sku_id."""

    def ensure_sales_order(self, draft: ErpSalesOrderDraft, *, customer: str, item_codes: dict[UUID, str]) -> str:
        """Return Sales Order name. Idempotent on runtime_order_id. Draft only."""


class ErpReadGateway(Protocol):
    def fetch_sales_order(self, runtime_order_id: UUID) -> dict | None:
        """Return Adapter-internal SO dict or None. May raise ErpGatewayError."""

    def list_draft_sales_orders(self, runtime_customer_id: UUID) -> list[dict]:
        """Draft SOs for a mapped customer. May raise ErpGatewayError."""
