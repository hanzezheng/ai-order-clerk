from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from app.bootstrap import build_app_world, new_session
from app.database.memory import PEAR, PEAR_SKU, WANG_JI
from app.database.postgres.factory import postgres_bundle
from app.entity.catalog import CustomerProfile, CustomerRecord
from app.entity.events import ORDER_CONFIRMED, OutboxRecord, aggregate_type_for
from app.entity.intake import IntakeReceipt
from app.entity.memory import PriceMemoryRecord
from app.entity.session import SalesSession
from app.entity.timeline import TimelineEvent
from app.main import create_app
from app.memory.evidence import EvidenceStore
from app.services.ports import MEMORY_EXTRACTOR_CONSUMER, TIMELINE_CONSUMER
from app.tests.pgutil import postgres_url_or_skip


def _client(world) -> TestClient:
    return TestClient(create_app(world))


def _turn(client: TestClient, session_id: str, text: str, *, seq: int, utterance_id: str):
    return client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "text": text,
            "source": "text",
            "utterance_id": utterance_id,
            "seq": seq,
            "is_final": True,
            "expect_more": False,
        },
    )


def _new_world(url: str, *, reset: bool):
    return build_app_world(database_url=url, reset_schema=reset)


def _dispose(world) -> None:
    if world.engine is not None:
        world.engine.dispose()


def _confirm_wang_ji_pear(client: TestClient, *, tag: str) -> str:
    created = client.post("/v1/workbench/tasks")
    assert created.status_code == 201
    session_id = created.json()["current_session_id"]
    assert _turn(client, session_id, "开王老板的单", seq=1, utterance_id=f"{tag}-start").status_code == 200
    assert _turn(client, session_id, "王记水果店", seq=2, utterance_id=f"{tag}-who").status_code == 200
    assert _turn(client, session_id, "梨60件", seq=3, utterance_id=f"{tag}-pear").status_code == 200
    done = _turn(client, session_id, "好了", seq=4, utterance_id=f"{tag}-ok")
    assert done.status_code == 200
    assert done.json()["verdict"]["confirm_ok"] is True
    return session_id


def test_postgres_ports_roundtrip():
    url = postgres_url_or_skip()
    world = _new_world(url, reset=True)
    assert world.engine is not None
    bundle = postgres_bundle(world.engine)
    customer_id = uuid4()
    bundle.catalog.put_customer(
        CustomerRecord(id=customer_id, legal_name="周记", display_name="周老板", stall_no="12"),
        CustomerProfile(customer_id=customer_id, display_name="周老板", stall_no="12"),
    )
    bundle.catalog.put_product_default(customer_id, PEAR, PEAR_SKU)
    stored = bundle.catalog.get_profile(customer_id)
    assert stored is not None
    assert stored.product_defaults[str(PEAR)] == PEAR_SKU
    bundle.aliases.put("梨儿", PEAR_SKU)
    assert bundle.aliases.get("梨儿") == PEAR_SKU
    bundle.prices.put(
        PriceMemoryRecord(
            price_type="last_deal",
            customer_id=WANG_JI,
            product_id=PEAR_SKU,
            unit_price=Decimal("3"),
            price_uom="块",
        )
    )
    assert bundle.prices.snapshot()[0].unit_price == Decimal("3")
    store = EvidenceStore(bundle.evidence)
    store.observe(customer_id=WANG_JI, kind="product_default", node_id=PEAR, sku_id=PEAR_SKU)
    store.observe(customer_id=WANG_JI, kind="product_default", node_id=PEAR, sku_id=PEAR_SKU)
    got = bundle.evidence.get(customer_id=WANG_JI, kind="product_default", node_id=PEAR, sku_id=PEAR_SKU)
    assert got is not None
    assert got.count == 2
    session = SalesSession()
    bundle.sessions.save(session)
    assert bundle.sessions.get(session.session_id) is not None
    bundle.orders.save_draft(session.draft)
    assert bundle.orders.get_draft(session.draft.order_id) is not None
    event = TimelineEvent(session_id=session.session_id, event_type="order.started", payload={"n": 1})
    bundle.timeline.append(event)
    assert bundle.timeline.list(session.session_id)[0].event_type == "order.started"
    bundle.processed.mark(TIMELINE_CONSUMER, event.event_id)
    assert bundle.processed.has(TIMELINE_CONSUMER, event.event_id) is True
    assert bundle.processed.has(MEMORY_EXTRACTOR_CONSUMER, event.event_id) is False
    shift = bundle.workbench.get_shift()
    shift.current_session_id = session.session_id
    bundle.workbench.save_shift(shift)
    assert bundle.workbench.get_shift().current_session_id == session.session_id
    bundle.receipts.put(
        IntakeReceipt(session_id=session.session_id, utterance_id="u1", payload={"ok": True})
    )
    bundle.receipts.set_last_seq(session.session_id, 2)
    receipt = bundle.receipts.get(session.session_id, "u1")
    assert receipt is not None
    assert receipt.payload == {"ok": True}
    assert bundle.receipts.last_seq(session.session_id) == 2
    outbox_id = uuid4()
    outbox_row = OutboxRecord(
        event_id=outbox_id,
        event_type=ORDER_CONFIRMED,
        aggregate_type=aggregate_type_for(ORDER_CONFIRMED),
        aggregate_id=session.draft.order_id,
        session_id=session.session_id,
        payload={"session_id": str(session.session_id)},
    )
    bundle.outbox.append(outbox_row)
    assert bundle.outbox.get(outbox_id) is not None
    assert bundle.outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER)[0].event_id == outbox_id
    bundle.processed.mark(MEMORY_EXTRACTOR_CONSUMER, outbox_id)
    assert bundle.outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER) == []
    assert bundle.outbox.list_pending(TIMELINE_CONSUMER)[0].event_id == outbox_id
    _dispose(world)


def test_kill_restart_keeps_customer_evidence_workbench_and_open_session():
    url = postgres_url_or_skip()
    world1 = _new_world(url, reset=True)
    client1 = _client(world1)

    cold = new_session()
    world1.runner.handle(cold, "开赵老板的单")
    world1.runner.handle(cold, "12号档")
    created = [
        c
        for c in world1.catalog.list_customers()
        if "赵老板" in {c.display_name, c.legal_name, *c.aliases}
    ]
    assert len(created) == 1
    zhao_id = created[0].id
    assert created[0].status == "candidate"

    first = _confirm_wang_ji_pear(client1, tag="r1")
    second = _confirm_wang_ji_pear(client1, tag="r2")
    profile = world1.catalog.get_profile(WANG_JI)
    assert profile is not None
    assert str(PEAR) not in profile.product_defaults

    open_task = client1.post("/v1/workbench/tasks")
    assert open_task.status_code == 201
    open_id = open_task.json()["current_session_id"]
    assert _turn(client1, open_id, "开李老板的单", seq=1, utterance_id="open-start").status_code == 200
    assert _turn(client1, open_id, "苹果60件", seq=2, utterance_id="open-apple").status_code == 200
    bench = client1.get("/v1/workbench").json()
    assert bench["current_session_id"] == open_id
    statuses = {item["session_id"]: item["status"] for item in bench["tasks"]}
    assert statuses[first] == "confirmed"
    assert statuses[second] == "confirmed"
    assert statuses[open_id] == "drafting"

    assert world1.engine is not None
    evidence_before = postgres_bundle(world1.engine).evidence.get(
        customer_id=WANG_JI, kind="product_default", node_id=PEAR, sku_id=PEAR_SKU
    )
    assert evidence_before is not None
    assert evidence_before.count == 2
    _dispose(world1)

    world2 = _new_world(url, reset=False)
    client2 = _client(world2)
    zhao = world2.catalog.get_customer(zhao_id)
    assert zhao is not None
    assert zhao.stall_no == "12"
    assert zhao.status == "candidate"

    assert world2.engine is not None
    evidence_after = postgres_bundle(world2.engine).evidence.get(
        customer_id=WANG_JI, kind="product_default", node_id=PEAR, sku_id=PEAR_SKU
    )
    assert evidence_after is not None
    assert evidence_after.count == 2
    assert evidence_after.positive_count == 2
    profile = world2.catalog.get_profile(WANG_JI)
    assert profile is not None
    assert str(PEAR) not in profile.product_defaults

    snap = client2.get(f"/v1/sessions/{open_id}").json()
    assert snap["draft"]["status"] != "confirmed"
    assert len(snap["draft"]["lines"]) == 1
    bench = client2.get("/v1/workbench").json()
    assert bench["current_session_id"] == open_id
    ids = {item["session_id"] for item in bench["tasks"]}
    assert {first, second, open_id} <= ids

    blocked = _turn(client2, first, "苹果60件", seq=5, utterance_id="after-restart")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "task_completed"

    cached = _turn(client2, open_id, "苹果60件", seq=2, utterance_id="open-apple")
    assert cached.status_code == 200

    _confirm_wang_ji_pear(client2, tag="r3")
    upgraded = world2.catalog.get_profile(WANG_JI)
    assert upgraded is not None
    assert upgraded.product_defaults[str(PEAR)] == PEAR_SKU
    evidence_third = postgres_bundle(world2.engine).evidence.get(
        customer_id=WANG_JI, kind="product_default", node_id=PEAR, sku_id=PEAR_SKU
    )
    assert evidence_third is not None
    assert evidence_third.count == 3
    _dispose(world2)


def test_seed_does_not_clobber_learned_profile_on_restart():
    url = postgres_url_or_skip()
    world1 = _new_world(url, reset=True)
    client1 = _client(world1)
    for idx in range(3):
        _confirm_wang_ji_pear(client1, tag=f"s{idx}")
    profile = world1.catalog.get_profile(WANG_JI)
    assert profile is not None
    assert profile.product_defaults[str(PEAR)] == PEAR_SKU
    _dispose(world1)

    world2 = _new_world(url, reset=False)
    profile = world2.catalog.get_profile(WANG_JI)
    assert profile is not None
    assert profile.product_defaults[str(PEAR)] == PEAR_SKU
    _dispose(world2)
