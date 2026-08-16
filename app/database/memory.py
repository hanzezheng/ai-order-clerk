from __future__ import annotations

from uuid import UUID, uuid5, NAMESPACE_DNS

from app.entity.catalog import CustomerProfile, CustomerRecord, ProductNode
from app.entity.intake import IntakeReceipt
from app.entity.memory import EvidenceRecord, PriceMemoryRecord
from app.entity.events import OutboxRecord
from app.entity.order import DraftOrder
from app.entity.session import SalesSession
from app.entity.timeline import TimelineEvent
from app.entity.workbench import WorkbenchShift
from app.database.uow import InMemoryUnitOfWork
from app.services.ports import (
    AliasRepository,
    CatalogRepository,
    EvidenceRepository,
    IntakeReceiptRepository,
    OrderRepository,
    OutboxRepository,
    PriceMemoryRepository,
    ProcessedEventRepository,
    SessionRepository,
    TimelineRepository,
    WorkbenchRepository,
)


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
            attributes={"grade": "统货"},
            default_uom="件",
        ),
        ProductNode(id=PEAR, parent_id=FRUIT, level="variety", name="梨", aliases=["梨"], default_uom="件"),
        ProductNode(
            id=PEAR_SKU,
            parent_id=PEAR,
            level="sku",
            name="皇冠梨箱装",
            aliases=["皇冠梨"],
            attributes={"packing": "箱装"},
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


class InMemoryAliasStore(AliasRepository):
    """长期商品别名。Resolver 只读，写入必须经 MemoryService。"""

    def __init__(self) -> None:
        self._items: list[tuple[str, UUID]] = []

    def put(self, alias: str, node_id: UUID) -> None:
        self._items = [(name, nid) for name, nid in self._items if name != alias]
        self._items.append((alias, node_id))

    def get(self, alias: str) -> UUID | None:
        for name, node_id in self._items:
            if name == alias:
                return node_id
        return None

    def snapshot(self) -> list[tuple[str, UUID]]:
        return list(self._items)


class InMemoryPriceStore(PriceMemoryRepository):
    """价格记忆。禁止被订单确认直接写入。"""

    def __init__(self) -> None:
        self._items: list[PriceMemoryRecord] = []

    def put(self, record: PriceMemoryRecord) -> None:
        self._items = [
            item
            for item in self._items
            if not (
                item.price_type == record.price_type
                and item.customer_id == record.customer_id
                and item.product_id == record.product_id
            )
        ]
        self._items.append(record.model_copy(deep=True))

    def snapshot(self) -> list[PriceMemoryRecord]:
        return [item.model_copy(deep=True) for item in self._items]


class InMemoryCatalog(CatalogRepository):
    def __init__(self) -> None:
        self.customers = {c.id: c for c in default_customers()}
        self.nodes = {n.id: n for n in default_nodes()}
        self.profiles = default_profiles()
        self.aliases = InMemoryAliasStore()
        self.prices = InMemoryPriceStore()

    def list_customers(self) -> list[CustomerRecord]:
        return list(self.customers.values())

    def get_customer(self, customer_id: UUID) -> CustomerRecord | None:
        return self.customers.get(customer_id)

    def get_profile(self, customer_id: UUID) -> CustomerProfile | None:
        return self.profiles.get(customer_id)

    def put_product_default(self, customer_id: UUID, node_id: UUID, sku_id: UUID) -> None:
        profile = self.profiles.get(customer_id)
        if profile is None:
            return
        defaults = dict(profile.product_defaults)
        defaults[str(node_id)] = sku_id
        self.profiles[customer_id] = profile.model_copy(update={"product_defaults": defaults})

    def put_customer(self, customer: CustomerRecord, profile: CustomerProfile) -> None:
        self.customers[customer.id] = customer
        self.profiles[customer.id] = profile

    def list_nodes(self) -> list[ProductNode]:
        return list(self.nodes.values())

    def get_node(self, node_id: UUID) -> ProductNode | None:
        return self.nodes.get(node_id)


class InMemorySessions(SessionRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, SalesSession] = {}

    def get(self, session_id: UUID) -> SalesSession | None:
        item = self._items.get(session_id)
        return item.model_copy(deep=True) if item is not None else None

    def save(self, session: SalesSession) -> None:
        self._items[session.session_id] = session.model_copy(deep=True)


class InMemoryOrders(OrderRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, DraftOrder] = {}

    def save_draft(self, draft: DraftOrder) -> None:
        self._items[draft.order_id] = draft.model_copy(deep=True)

    def get_draft(self, order_id: UUID) -> DraftOrder | None:
        item = self._items.get(order_id)
        return item.model_copy(deep=True) if item is not None else None


class InMemoryEvidence(EvidenceRepository):
    def __init__(self) -> None:
        self._items: dict[tuple[UUID, str, UUID, UUID], EvidenceRecord] = {}

    def get(
        self,
        *,
        customer_id: UUID,
        kind: str,
        node_id: UUID,
        sku_id: UUID,
    ) -> EvidenceRecord | None:
        item = self._items.get((customer_id, kind, node_id, sku_id))
        return item.model_copy(deep=True) if item is not None else None

    def put(self, record: EvidenceRecord) -> None:
        key = (record.customer_id, record.kind, record.node_id, record.sku_id)
        self._items[key] = record.model_copy(deep=True)


class InMemoryTimeline(TimelineRepository):
    def __init__(self) -> None:
        self._items: dict[UUID, list[TimelineEvent]] = {}

    def list(self, session_id: UUID) -> list[TimelineEvent]:
        return [item.model_copy(deep=True) for item in self._items.get(session_id, [])]

    def append(self, event: TimelineEvent) -> TimelineEvent:
        stored = event.model_copy(deep=True)
        self._items.setdefault(event.session_id, []).append(stored)
        return stored.model_copy(deep=True)


class InMemoryProcessedEvents(ProcessedEventRepository):
    def __init__(self) -> None:
        self._items: set[tuple[str, UUID]] = set()

    def has(self, consumer: str, event_id: UUID) -> bool:
        return (consumer, event_id) in self._items

    def mark(self, consumer: str, event_id: UUID) -> None:
        self._items.add((consumer, event_id))


class InMemoryWorkbench(WorkbenchRepository):
    def __init__(self) -> None:
        self._shift = WorkbenchShift()

    def get_shift(self) -> WorkbenchShift:
        return self._shift.model_copy(deep=True)

    def save_shift(self, shift: WorkbenchShift) -> None:
        self._shift = shift.model_copy(deep=True)


class InMemoryIntakeReceipts(IntakeReceiptRepository):
    def __init__(self) -> None:
        self._receipts: dict[tuple[UUID, str], IntakeReceipt] = {}
        self._last_seq: dict[UUID, int] = {}

    def get(self, session_id: UUID, utterance_id: str) -> IntakeReceipt | None:
        item = self._receipts.get((session_id, utterance_id))
        return item.model_copy(deep=True) if item is not None else None

    def put(self, receipt: IntakeReceipt) -> None:
        self._receipts[(receipt.session_id, receipt.utterance_id)] = receipt.model_copy(deep=True)

    def last_seq(self, session_id: UUID) -> int | None:
        return self._last_seq.get(session_id)

    def set_last_seq(self, session_id: UUID, seq: int) -> None:
        self._last_seq[session_id] = seq


class InMemoryOutbox(OutboxRepository):
    def __init__(self, uow: InMemoryUnitOfWork, processed: ProcessedEventRepository) -> None:
        self._committed: list[OutboxRecord] = []
        self._staged: list[OutboxRecord] = []
        self._uow = uow
        self._processed = processed
        uow.on_commit(self._flush)
        uow.on_rollback(self._clear_staged)

    def append(self, record: OutboxRecord) -> None:
        stored = record.model_copy(deep=True)
        if self._uow.active():
            self._staged.append(stored)
        else:
            self._committed.append(stored)

    def get(self, event_id: UUID) -> OutboxRecord | None:
        for item in (*self._committed, *self._staged):
            if item.event_id == event_id:
                return item.model_copy(deep=True)
        return None

    def list_pending(
        self,
        consumer: str,
        *,
        event_types: tuple[str, ...] | None = None,
        limit: int = 500,
    ) -> list[OutboxRecord]:
        out: list[OutboxRecord] = []
        for item in sorted(self._committed, key=lambda row: (row.recorded_at, row.event_id)):
            if self._processed.has(consumer, item.event_id):
                continue
            if event_types is not None and item.event_type not in event_types:
                continue
            out.append(item.model_copy(deep=True))
            if len(out) >= limit:
                break
        return out

    def _flush(self) -> None:
        self._committed.extend(self._staged)
        self._staged = []

    def _clear_staged(self) -> None:
        self._staged = []
