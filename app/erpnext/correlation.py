from __future__ import annotations

from uuid import UUID


class InMemoryCorrelationStore:
    """Adapter 私有对照。禁止写入 Catalog / OrderLine。"""

    def __init__(self) -> None:
        self.customers: dict[UUID, str] = {}
        self.items: dict[UUID, str] = {}
        self.orders: dict[UUID, str] = {}

    def customer(self, runtime_customer_id: UUID) -> str | None:
        return self.customers.get(runtime_customer_id)

    def put_customer(self, runtime_customer_id: UUID, erp_name: str) -> None:
        self.customers[runtime_customer_id] = erp_name

    def item(self, runtime_sku_id: UUID) -> str | None:
        return self.items.get(runtime_sku_id)

    def put_item(self, runtime_sku_id: UUID, item_code: str) -> None:
        self.items[runtime_sku_id] = item_code

    def order(self, runtime_order_id: UUID) -> str | None:
        return self.orders.get(runtime_order_id)

    def put_order(self, runtime_order_id: UUID, sales_order: str) -> None:
        self.orders[runtime_order_id] = sales_order
