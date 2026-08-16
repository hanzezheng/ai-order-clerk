from __future__ import annotations

from uuid import UUID, uuid5, NAMESPACE_DNS

from app.entity.catalog import CustomerProfile, CustomerRecord, ProductNode
from app.entity.order import DraftOrder
from app.entity.session import SalesSession
from app.services.ports import CatalogRepository, OrderRepository, SessionRepository


def uid(key: str) -> UUID:
    return uuid5(NAMESPACE_DNS, f"ai-order-clerk:{key}")


FRUIT = uid("node:fruit")
APPLE = uid("node:apple")
FUJI = uid("node:fuji")
FUJI80 = uid("node:fuji80")
GREEN = uid("node:green")
GREEN_SKU = uid("node:green-sku")
PEAR = uid("node:pear")
PEAR_SKU = uid("node:pear-sku")
DURIAN = uid("node:durian")
GOLDEN = uid("node:golden")
GOLDEN_SKU = uid("node:golden-sku")

WANG_QIANG = uid("customer:wang-qiang")
WANG_JI = uid("customer:wang-ji")
LI_BOSS = uid("customer:li")


def default_nodes() -> list[ProductNode]:
    return [
        ProductNode(id=FRUIT, level="category", name="水果", aliases=["水果"], default_uom="件"),
        ProductNode(id=APPLE, parent_id=FRUIT, level="variety", name="苹果", aliases=["苹果"], default_uom="件"),
        ProductNode(id=FUJI, parent_id=APPLE, level="cultivar", name="红富士", aliases=["红富士"], default_uom="件"),
        ProductNode(
            id=FUJI80,
            parent_id=FUJI,
            level="sku",
            name="红富士80果一级烟台箱装",
            aliases=["红富士80", "八零果", "80果", "八十果"],
            attributes={"grade": "一级", "size": "80", "origin": "烟台", "packing": "箱装"},
            default_uom="件",
        ),
        ProductNode(id=GREEN, parent_id=APPLE, level="cultivar", name="青苹果", aliases=["青苹果"], default_uom="件"),
        ProductNode(
            id=GREEN_SKU,
            parent_id=GREEN,
            level="sku",
            name="青苹果统货",
            aliases=["青苹果统货"],
            default_uom="件",
        ),
        ProductNode(id=PEAR, parent_id=FRUIT, level="variety", name="梨", aliases=["梨"], default_uom="件"),
        ProductNode(
            id=PEAR_SKU,
            parent_id=PEAR,
            level="sku",
            name="皇冠梨箱装",
            aliases=["皇冠梨"],
            default_uom="件",
        ),
        ProductNode(id=DURIAN, parent_id=FRUIT, level="variety", name="榴莲", aliases=["榴莲"], default_uom="个"),
        ProductNode(
            id=GOLDEN,
            parent_id=DURIAN,
            level="cultivar",
            name="金边",
            aliases=["金边", "金边榴莲"],
            default_uom="个",
        ),
        ProductNode(
            id=GOLDEN_SKU,
            parent_id=GOLDEN,
            level="sku",
            name="金边榴莲果",
            aliases=["金边榴莲果"],
            default_uom="个",
        ),
    ]


def default_customers() -> list[CustomerRecord]:
    return [
        CustomerRecord(
            id=WANG_QIANG,
            legal_name="王强水果店",
            display_name="王老板",
            stall_no="3",
            phones=["13800000003"],
            aliases=["王老板", "老王", "王强"],
        ),
        CustomerRecord(
            id=WANG_JI,
            legal_name="王记水果店",
            display_name="王老板",
            stall_no="8",
            phones=["13800000008"],
            aliases=["王老板", "王记"],
        ),
        CustomerRecord(
            id=LI_BOSS,
            legal_name="李记果行",
            display_name="李老板",
            stall_no="1",
            phones=["13900000001"],
            aliases=["李老板", "老李"],
        ),
    ]


def default_profiles() -> dict[UUID, CustomerProfile]:
    wang = default_customers()[0]
    li = default_customers()[2]
    return {
        WANG_QIANG: CustomerProfile(
            customer_id=WANG_QIANG,
            display_name=wang.display_name,
            stall_no=wang.stall_no,
            phones=wang.phones,
            product_defaults={str(APPLE): FUJI80},
        ),
        WANG_JI: CustomerProfile(
            customer_id=WANG_JI,
            display_name="王老板",
            stall_no="8",
            phones=["13800000008"],
            product_defaults={},
        ),
        LI_BOSS: CustomerProfile(
            customer_id=LI_BOSS,
            display_name=li.display_name,
            stall_no=li.stall_no,
            phones=li.phones,
            product_defaults={str(APPLE): FUJI80},
        ),
    }


class InMemoryCatalog(CatalogRepository):
    def __init__(self) -> None:
        self.customers = {c.id: c for c in default_customers()}
        self.nodes = {n.id: n for n in default_nodes()}
        self.profiles = default_profiles()

    def list_customers(self) -> list[CustomerRecord]:
        return list(self.customers.values())

    def get_customer(self, customer_id: UUID) -> CustomerRecord | None:
        return self.customers.get(customer_id)

    def get_profile(self, customer_id: UUID) -> CustomerProfile | None:
        return self.profiles.get(customer_id)

    def list_nodes(self) -> list[ProductNode]:
        return list(self.nodes.values())

    def get_node(self, node_id: UUID) -> ProductNode | None:
        return self.nodes.get(node_id)


class InMemorySessions(SessionRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, SalesSession] = {}

    def get(self, session_id: UUID) -> SalesSession | None:
        return self._items.get(session_id)

    def save(self, session: SalesSession) -> None:
        self._items[session.session_id] = session.model_copy(deep=True)


class InMemoryOrders(OrderRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, DraftOrder] = {}

    def save_draft(self, draft: DraftOrder) -> None:
        self._items[draft.order_id] = draft.model_copy(deep=True)

    def get_draft(self, order_id: UUID) -> DraftOrder | None:
        return self._items.get(order_id)
