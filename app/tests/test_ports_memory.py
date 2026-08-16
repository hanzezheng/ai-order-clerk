from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from app.database.memory import (
    InMemoryAliasStore,
    InMemoryCatalog,
    InMemoryEvidence,
    InMemoryIntakeReceipts,
    InMemoryOrders,
    InMemoryProcessedEvents,
    InMemorySessions,
    InMemoryTimeline,
    InMemoryWorkbench,
    InMemoryPriceStore,
    PEAR,
    PEAR_SKU,
    WANG_JI,
)
from app.entity.catalog import CustomerProfile, CustomerRecord
from app.entity.intake import IntakeReceipt
from app.entity.memory import EvidenceRecord, PriceMemoryRecord
from app.entity.session import SalesSession
from app.entity.timeline import TimelineEvent
from app.memory.evidence import EvidenceStore
from app.services.ports import MEMORY_EXTRACTOR_CONSUMER, TIMELINE_CONSUMER

BUSINESS_DIRS = ("agent", "policy", "memory", "response", "services", "session", "workbench", "entity", "api")
FORBIDDEN_IMPORTS = (
    "from app.database",
    "import app.database",
    "InMemoryAliasStore",
    "InMemoryPriceStore",
    "InMemoryCatalog",
    "InMemorySessions",
    "InMemoryOrders",
    "InMemoryEvidence",
    "InMemoryTimeline",
    "InMemoryProcessedEvents",
    "InMemoryWorkbench",
    "InMemoryIntakeReceipts",
)


def test_business_layer_does_not_depend_on_inmemory():
    root = Path(__file__).resolve().parents[1]
    offenders: list[str] = []
    for folder in BUSINESS_DIRS:
        for path in (root / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            for needle in FORBIDDEN_IMPORTS:
                if needle in text:
                    offenders.append(f"{path.relative_to(root.parent)}: {needle}")
    assert offenders == []


def test_catalog_write_put_customer_and_product_default():
    catalog = InMemoryCatalog()
    customer_id = uuid4()
    record = CustomerRecord(
        id=customer_id,
        legal_name="周记",
        display_name="周老板",
        stall_no="12",
        aliases=["周老板"],
        status="candidate",
    )
    profile = CustomerProfile(customer_id=customer_id, display_name="周老板", stall_no="12")
    catalog.put_customer(record, profile)
    assert catalog.get_customer(customer_id) is not None
    catalog.put_product_default(customer_id, PEAR, PEAR_SKU)
    stored = catalog.get_profile(customer_id)
    assert stored is not None
    assert stored.product_defaults[str(PEAR)] == PEAR_SKU
    catalog.put_product_default(WANG_JI, PEAR, PEAR_SKU)
    wang = catalog.get_profile(WANG_JI)
    assert wang is not None
    assert wang.product_defaults[str(PEAR)] == PEAR_SKU


def test_alias_and_price_ports():
    aliases = InMemoryAliasStore()
    prices = InMemoryPriceStore()
    node_id = uuid4()
    aliases.put("八零果", node_id)
    assert aliases.get("八零果") == node_id
    aliases.put("八零果", PEAR_SKU)
    assert aliases.get("八零果") == PEAR_SKU
    assert aliases.snapshot() == [("八零果", PEAR_SKU)]
    rec = PriceMemoryRecord(
        price_type="last_deal",
        customer_id=WANG_JI,
        product_id=PEAR_SKU,
        unit_price=Decimal("3"),
        price_uom="块",
    )
    prices.put(rec)
    snap = prices.snapshot()
    assert len(snap) == 1
    assert snap[0].unit_price == Decimal("3")
    prices.put(rec.model_copy(update={"unit_price": Decimal("4")}))
    assert prices.snapshot()[0].unit_price == Decimal("4")


def test_evidence_port_keeps_adjust_rules():
    repo = InMemoryEvidence()
    store = EvidenceStore(repo)
    customer_id = uuid4()
    node_id = uuid4()
    sku_id = uuid4()
    missing = store.adjust(
        customer_id=customer_id,
        kind="product_default",
        node_id=node_id,
        sku_id=sku_id,
        delta=-1,
    )
    assert missing.count == 0
    assert missing.negative_count == 1
    rebuilt = EvidenceStore(repo)
    again = rebuilt.get(customer_id=customer_id, kind="product_default", node_id=node_id, sku_id=sku_id)
    assert again is not None
    assert again.negative_count == 1
    rebuilt.observe(customer_id=customer_id, kind="product_default", node_id=node_id, sku_id=sku_id)
    persisted = repo.get(customer_id=customer_id, kind="product_default", node_id=node_id, sku_id=sku_id)
    assert persisted is not None
    assert persisted.count == 1


def test_timeline_and_processed_event_ports():
    timeline = InMemoryTimeline()
    processed = InMemoryProcessedEvents()
    session_id = uuid4()
    event_id = uuid4()
    stored = timeline.append(
        TimelineEvent(event_id=event_id, session_id=session_id, event_type="order.confirmed", payload={"n": 1})
    )
    assert stored.event_id == event_id
    assert timeline.list(session_id)[0].payload == {"n": 1}
    assert processed.has(TIMELINE_CONSUMER, event_id) is False
    processed.mark(TIMELINE_CONSUMER, event_id)
    assert processed.has(TIMELINE_CONSUMER, event_id) is True
    assert processed.has(MEMORY_EXTRACTOR_CONSUMER, event_id) is False


def test_workbench_session_order_and_intake_ports():
    workbench = InMemoryWorkbench()
    sessions = InMemorySessions()
    orders = InMemoryOrders()
    receipts = InMemoryIntakeReceipts()
    session = SalesSession()
    sessions.save(session)
    loaded = sessions.get(session.session_id)
    assert loaded is not None
    assert loaded.session_id == session.session_id
    orders.save_draft(session.draft)
    assert orders.get_draft(session.draft.order_id) is not None
    shift = workbench.get_shift()
    shift.current_session_id = session.session_id
    workbench.save_shift(shift)
    assert workbench.get_shift().current_session_id == session.session_id
    receipts.put(
        IntakeReceipt(
            session_id=session.session_id,
            utterance_id="u1",
            payload={"ignored": False},
        )
    )
    receipts.set_last_seq(session.session_id, 3)
    got = receipts.get(session.session_id, "u1")
    assert got is not None
    assert got.payload == {"ignored": False}
    assert receipts.last_seq(session.session_id) == 3


def test_evidence_put_roundtrip_record():
    repo = InMemoryEvidence()
    record = EvidenceRecord(
        customer_id=WANG_JI,
        kind="product_default",
        node_id=PEAR,
        sku_id=PEAR_SKU,
        count=2,
        positive_count=2,
        status="pending",
    )
    repo.put(record)
    got = repo.get(customer_id=WANG_JI, kind="product_default", node_id=PEAR, sku_id=PEAR_SKU)
    assert got is not None
    assert got.count == 2
    got.count = 99
    again = repo.get(customer_id=WANG_JI, kind="product_default", node_id=PEAR, sku_id=PEAR_SKU)
    assert again is not None
    assert again.count == 2
