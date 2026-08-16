from decimal import Decimal

from app.bootstrap import build_world, new_session
from app.database.memory import APPLE, FUJI80, GREEN_SKU, LI_BOSS, PEAR, PEAR_SKU, WANG_JI
from app.entity.events import ORDER_CONFIRMED


def test_quantity_is_not_stored_as_memory():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    runner.handle(session, "好了")
    assert catalog.aliases.snapshot() == []
    profile = catalog.get_profile(LI_BOSS)
    assert profile is not None
    assert profile.product_defaults[str(APPLE)] == FUJI80


def test_temp_spec_change_does_not_pollute_profile():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    runner.handle(session, "青苹果60件")
    line = session.draft.lines[0]
    assert line.product_sku_id == GREEN_SKU
    profile = catalog.get_profile(LI_BOSS)
    assert profile is not None
    assert profile.product_defaults[str(APPLE)] == FUJI80


def test_one_green_apple_confirm_does_not_overwrite_fuji_default():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "青苹果60件")
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    profile = catalog.get_profile(LI_BOSS)
    assert profile is not None
    assert profile.product_defaults[str(APPLE)] == FUJI80


def test_unbound_customer_cannot_write_memory():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开王老板的单")
    runner.handle(session, "苹果60件")
    assert catalog.aliases.snapshot() == []
    assert catalog.prices.snapshot() == []


def test_tbd_confirm_does_not_write_last_deal():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    runner.handle(session, "好了")
    assert [p for p in catalog.prices.snapshot() if p.price_type == "last_deal"] == []


def test_explicit_price_writes_last_deal_only_after_confirm():
    runner, events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果按3块")
    assert catalog.prices.snapshot() == []
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    assert any(e.event_type == ORDER_CONFIRMED for e in events.events)
    deals = [p for p in catalog.prices.snapshot() if p.price_type == "last_deal"]
    assert len(deals) == 1
    assert deals[0].unit_price == Decimal("3")
    assert deals[0].product_id == FUJI80
    assert deals[0].customer_id == LI_BOSS
    assert deals[0].status == "active"
    assert deals[0].last_confirmed_at is not None


def _confirm_wang_ji_pear(runner):
    session = new_session()
    runner.handle(session, "开王老板的单")
    runner.handle(session, "王记水果店")
    runner.handle(session, "梨60件")
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    assert session.draft.customer is not None
    assert session.draft.customer.id == WANG_JI
    return session


def test_product_default_requires_three_confirm_evidence():
    runner, _events, catalog = build_world()
    profile = catalog.get_profile(WANG_JI)
    assert profile is not None
    assert profile.product_defaults == {}
    _confirm_wang_ji_pear(runner)
    _confirm_wang_ji_pear(runner)
    assert catalog.get_profile(WANG_JI).product_defaults == {}
    _confirm_wang_ji_pear(runner)
    defaults = catalog.get_profile(WANG_JI).product_defaults
    assert defaults[str(PEAR)] == PEAR_SKU
