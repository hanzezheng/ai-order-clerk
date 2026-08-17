from __future__ import annotations

from app.bootstrap import build_app_world, new_session
from app.database.memory import LI_BOSS
from app.entity.context import BusinessContext
from app.erpnext.fake import FakeErpGateway
from app.erpnext.read import ErpnextReadAdapter
from app.tests.test_api_turns import _client, _open_session, _turn
from app.tests.test_erpnext_adapter import _confirm_li_apple


def test_draft_session_has_no_enterprise_and_does_not_read_erp():
    world = build_app_world()
    session = new_session()
    world.sessions.save(session)
    world.runner.handle(session, "开李老板的单")
    world.runner.handle(session, "苹果60件")
    assert session.draft.status == "draft"
    reads = [name for name in world.erpnext.calls if name.startswith("fetch") or name.startswith("list_draft")]
    assert reads == []
    fact = world.facts.posting_for(session.draft.order_id)
    assert fact.posting == "pending"
    assert fact.prices_incomplete is None


def test_confirmed_order_projects_posted_without_erp_fields():
    world = build_app_world()
    done = _confirm_li_apple(world)
    fact = world.facts.posting_for(done.session.draft.order_id)
    assert fact.posting == "posted"
    assert fact.prices_incomplete is True
    assert fact.line_count == 1
    public = fact.public()
    assert "item_code" not in public
    assert "doctype" not in public
    assert "warehouse" not in public
    assert "name" not in public
    assert world.facts.open_draft_count(LI_BOSS) == 1


def test_read_failure_is_unavailable_and_does_not_change_confirm():
    world = build_app_world()
    done = _confirm_li_apple(world)
    assert done.verdict.confirm_ok is True
    world.erpnext.fail_next_read = True
    fact = world.facts.posting_for(done.session.draft.order_id)
    assert fact.posting == "unavailable"
    live = world.sessions.get(done.session.session_id)
    assert live is not None
    assert live.draft.status == "confirmed"
    assert done.verdict.confirm_ok is True


def test_write_failure_projects_pending_then_posted_after_recover():
    world = build_app_world()
    world.erpnext.fail_next = True
    done = _confirm_li_apple(world)
    assert done.session.draft.status == "confirmed"
    assert world.facts.posting_for(done.session.draft.order_id).posting == "pending"
    world.events.recover()
    assert world.facts.posting_for(done.session.draft.order_id).posting == "posted"


def test_http_session_projection_and_workbench_posting():
    client = _client()
    world = client.app.state.world
    assert isinstance(world.erpnext, FakeErpGateway)
    session_id = _open_session(client)
    draft = client.get(f"/v1/sessions/{session_id}").json()
    assert draft["enterprise"] is None
    assert "item_code" not in str(draft["draft"])
    _turn(client, session_id, "开李老板的单", seq=1, utterance_id="r1")
    _turn(client, session_id, "苹果60件", seq=2, utterance_id="r2")
    done = _turn(client, session_id, "好了", seq=3, utterance_id="r3")
    assert done.status_code == 200
    body = done.json()
    assert body["verdict"]["confirm_ok"] is True
    assert body["enterprise"]["posting"] == "posted"
    assert body["enterprise"]["prices_incomplete"] is True
    assert "item_code" not in body["enterprise"]
    assert "SO-" not in body["reply_text"]
    snap = client.get(f"/v1/sessions/{session_id}").json()
    assert snap["enterprise"]["posting"] == "posted"
    assert "item_code" not in str(snap["draft"]["lines"])
    board = client.get("/v1/workbench").json()
    confirmed = next(task for task in board["tasks"] if task["session_id"] == session_id)
    assert confirmed["posting"] == "posted"
    assert board["open_draft_count"] == 1


def test_http_read_failure_keeps_confirmed_and_returns_unavailable():
    client = _client()
    world = client.app.state.world
    session_id = _open_session(client)
    _turn(client, session_id, "开李老板的单", seq=1, utterance_id="f1")
    _turn(client, session_id, "苹果60件", seq=2, utterance_id="f2")
    done = _turn(client, session_id, "好了", seq=3, utterance_id="f3")
    assert done.json()["verdict"]["confirm_ok"] is True
    world.erpnext.fail_next_read = True
    snap = client.get(f"/v1/sessions/{session_id}").json()
    assert snap["draft"]["status"] == "confirmed"
    assert snap["enterprise"]["posting"] == "unavailable"
    assert snap["verdict"]["confirm_ok"] is True if "verdict" in snap else True


def test_business_context_shape_unchanged_after_confirm():
    world = build_app_world()
    _confirm_li_apple(world)
    assert list(BusinessContext.model_fields) == ["customer_id", "profile_defaults", "price_facts"]


def test_query_draft_does_not_speak_erp_names():
    world = build_app_world()
    _confirm_li_apple(world)
    session = new_session()
    world.sessions.save(session)
    world.runner.handle(session, "开李老板的单")
    world.runner.handle(session, "苹果60件")
    asked = world.runner.handle(session, "现在有啥")
    assert "SO-" not in asked.reply_text
    assert "item_code" not in asked.reply_text
    assert asked.verdict.confirm_ok is False


def test_read_adapter_does_not_call_write_ensure():
    world = build_app_world()
    adapter = ErpnextReadAdapter(world.erpnext)
    session = new_session()
    world.sessions.save(session)
    world.runner.handle(session, "开李老板的单")
    adapter.posting_for(session.draft.order_id)
    assert "ensure_sales_order" not in world.erpnext.calls
    assert "ensure_customer" not in world.erpnext.calls
