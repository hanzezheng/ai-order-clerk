from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request

from app.bootstrap import build_app_world, new_session
from app.database.memory import APPLE, FUJI80, LI_BOSS, PEAR_SKU, WANG_JI
from app.entity.events import ORDER_CONFIRMED
from app.erpnext.fake import FakeErpGateway
from app.erpnext.http import HttpErpGateway
from app.erpnext.mapper import ErpDraftMapper
from app.erpnext.ports import (
    ERPNEXT_ADAPTER_CONSUMER,
    ITEM_DOCTYPE,
    SALES_ORDER_DOCTYPE,
    ErpItemDraft,
    ErpSalesOrderDraft,
    ErpSalesOrderLine,
    item_code_for,
)
from app.services.ports import MEMORY_EXTRACTOR_CONSUMER, TIMELINE_CONSUMER
from app.tests.test_api_turns import _client, _open_session, _turn

ROOT = Path(__file__).resolve().parents[2]
FROZEN = [
    ROOT / "app/agent/parser.py",
    ROOT / "app/agent/llm_parser.py",
    ROOT / "app/services/product_understanding.py",
    ROOT / "app/services/product_resolver.py",
    ROOT / "app/policy/decision.py",
    ROOT / "app/services/order_service.py",
    ROOT / "app/memory/extractor.py",
    ROOT / "app/memory/policy.py",
    ROOT / "app/entity/order.py",
    ROOT / "app/entity/catalog.py",
    ROOT / "app/entity/speech.py",
]


def _confirm_li_apple(world):
    session = new_session()
    world.sessions.save(session)
    world.runner.handle(session, "开李老板的单")
    world.runner.handle(session, "苹果60件")
    done = world.runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    return done


def test_confirmed_order_creates_one_draft_sales_order():
    world = build_app_world()
    assert isinstance(world.erpnext, FakeErpGateway)
    done = _confirm_li_apple(world)
    gateway = world.erpnext
    assert len(gateway.sales_orders) == 1
    order = gateway.sales_orders[0]
    assert order["doctype"] == SALES_ORDER_DOCTYPE
    assert order["docstatus"] == 0
    assert order["status"] == "Draft"
    assert order["update_stock"] == 0
    assert "warehouse" not in order
    assert all("warehouse" not in line for line in order["items"])
    assert order["prices_incomplete"] is True
    assert order["runtime_order_id"] == str(done.session.draft.order_id)
    assert gateway.maps.customer(LI_BOSS) == order["customer"]
    assert gateway.maps.item(FUJI80) == order["items"][0]["item_code"]
    assert order["items"][0]["item_code"] == item_code_for(FUJI80)
    assert order["items"][0]["qty"] == "60"
    assert order["items"][0]["rate"] == "0"
    assert gateway.items[0]["doctype"] == ITEM_DOCTYPE
    assert gateway.items[0]["is_stock_item"] == 0
    assert world.outbox.list_pending(ERPNEXT_ADAPTER_CONSUMER, event_types=(ORDER_CONFIRMED,)) == []


def test_draft_turns_do_not_create_sales_order():
    world = build_app_world()
    session = new_session()
    world.sessions.save(session)
    world.runner.handle(session, "开李老板的单")
    world.runner.handle(session, "苹果60件")
    assert world.erpnext.sales_orders == []
    assert session.draft.status == "draft"


def test_event_id_and_order_id_are_idempotent():
    world = build_app_world()
    done = _confirm_li_apple(world)
    gateway = world.erpnext
    assert len(gateway.sales_orders) == 1
    world.events.drain(done.session)
    world.events.drain(done.session)
    assert len(gateway.sales_orders) == 1
    gateway.ensure_sales_order(
        ErpSalesOrderDraft(
            runtime_order_id=done.session.draft.order_id,
            runtime_customer_id=LI_BOSS,
            prices_incomplete=True,
            items=(
                ErpSalesOrderLine(
                    runtime_sku_id=FUJI80,
                    qty=done.session.draft.lines[0].qty.value,
                    uom="件",
                    rate=done.session.draft.lines[0].price.unit_price or 0,
                    price_tbd=True,
                ),
            ),
        ),
        customer=gateway.maps.customer(LI_BOSS),
        item_codes={FUJI80: item_code_for(FUJI80)},
    )
    assert len(gateway.sales_orders) == 1


def test_erp_failure_does_not_change_runtime_confirm():
    world = build_app_world()
    world.erpnext.fail_next = True
    done = _confirm_li_apple(world)
    assert done.verdict.confirm_ok is True
    assert done.session.draft.status == "confirmed"
    assert world.erpnext.sales_orders == []
    pending = world.outbox.list_pending(ERPNEXT_ADAPTER_CONSUMER, event_types=(ORDER_CONFIRMED,))
    assert len(pending) == 1
    assert world.outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER, event_types=(ORDER_CONFIRMED,)) == []
    assert world.outbox.list_pending(TIMELINE_CONSUMER) == []
    erp_consumer = next(item for item in world.events._consumers if item.name == ERPNEXT_ADAPTER_CONSUMER)
    assert erp_consumer.last_error == "erp_unavailable"
    world.events.recover()
    assert len(world.erpnext.sales_orders) == 1
    assert world.outbox.list_pending(ERPNEXT_ADAPTER_CONSUMER, event_types=(ORDER_CONFIRMED,)) == []
    live = world.sessions.get(done.session.session_id)
    assert live is not None
    assert live.draft.status == "confirmed"


def test_http_turns_confirm_still_succeeds_when_erp_fails():
    client = _client()
    world = client.app.state.world
    world.erpnext.fail_next = True
    session_id = _open_session(client)
    _turn(client, session_id, "开李老板的单", seq=1, utterance_id="e1")
    _turn(client, session_id, "苹果60件", seq=2, utterance_id="e2")
    done = _turn(client, session_id, "好了", seq=3, utterance_id="e3")
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["verdict"]["confirm_ok"] is True
    assert body["draft"]["status"] == "confirmed"
    assert world.erpnext.sales_orders == []


def test_wang_ji_maps_bound_customer_not_homonym():
    world = build_app_world()
    session = new_session()
    world.sessions.save(session)
    world.runner.handle(session, "开王老板的单")
    world.runner.handle(session, "王记水果店")
    world.runner.handle(session, "梨60件")
    done = world.runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    order = world.erpnext.sales_orders[0]
    assert world.erpnext.maps.customer(WANG_JI) == order["customer"]
    assert world.erpnext.maps.item(PEAR_SKU) == order["items"][0]["item_code"]
    assert "王强" not in world.erpnext.customers[0]["customer_name"]


def test_adapter_maps_leaf_sku_only_and_does_not_write_catalog():
    world = build_app_world()
    before = world.catalog.get_node(FUJI80)
    apple = world.catalog.get_node(APPLE)
    assert before is not None and apple is not None
    aliases = list(before.aliases)
    done = _confirm_li_apple(world)
    after = world.catalog.get_node(FUJI80)
    assert after is not None
    assert after.aliases == aliases
    assert after.name == before.name
    mapper = ErpDraftMapper(world.catalog)
    items = mapper.items(done.session)
    assert [item.runtime_sku_id for item in items] == [FUJI80]
    assert apple.id not in {item.runtime_sku_id for item in items}
    assert apple.level != "sku"


def test_http_gateway_posts_draft_sales_order_without_warehouse(monkeypatch):
    sent: list[bytes] = []

    def fake_urlopen(request: Request, timeout: float = 0):
        sent.append(request.data or b"")

        class Reply:
            def read(self) -> bytes:
                if request.method == "GET":
                    return b'{"data":[]}'
                payload = json.loads((request.data or b"{}").decode("utf-8"))
                return json.dumps({"data": {"name": payload.get("name") or payload.get("item_code")}}).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

        return Reply()

    monkeypatch.setattr("app.erpnext.http.urlopen", fake_urlopen)
    gateway = HttpErpGateway("http://erp.example")
    from decimal import Decimal

    from app.erpnext.ports import ErpCustomerDraft, ErpSalesOrderLine

    customer = gateway.ensure_customer(ErpCustomerDraft(runtime_customer_id=LI_BOSS, customer_name="李老板", stall_no="A1"))
    code = gateway.ensure_item(ErpItemDraft(runtime_sku_id=FUJI80, item_name="红富士80果一级烟台箱装", stock_uom="件"))
    name = gateway.ensure_sales_order(
        ErpSalesOrderDraft(
            runtime_order_id=LI_BOSS,
            runtime_customer_id=LI_BOSS,
            prices_incomplete=True,
            items=(ErpSalesOrderLine(runtime_sku_id=FUJI80, qty=Decimal("60"), uom="件", rate=Decimal("0"), price_tbd=True),),
        ),
        customer=customer,
        item_codes={FUJI80: code},
    )
    assert name.startswith("SO-")
    bodies = [json.loads(raw.decode("utf-8")) for raw in sent if raw]
    sales = next(item for item in bodies if item.get("doctype") == SALES_ORDER_DOCTYPE)
    assert sales["docstatus"] == 0
    assert sales["name"].startswith("SO-")
    assert "warehouse" not in sales
    assert "warehouse" not in sales["items"][0]
    assert "update_stock" not in sales
    assert sales["prices_incomplete"] is True
    assert all("warehouse" not in json.dumps(item) for item in bodies)


def test_frozen_runtime_has_no_erp_fields():
    needles = ("item_code", "doctype", "warehouse", "frappe", "erpnext")
    for path in FROZEN:
        text = path.read_text(encoding="utf-8").lower()
        for needle in needles:
            assert needle not in text, f"{path} contains {needle}"
