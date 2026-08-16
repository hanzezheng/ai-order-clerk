from app.bootstrap import build_world, new_session
from app.database.memory import APPLE, FUJI80, GREEN_SKU, LI_BOSS


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


def test_unbound_customer_cannot_write_memory():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开王老板的单")
    runner.handle(session, "苹果60件")
    assert catalog.aliases.snapshot() == []
    assert catalog.prices.snapshot() == []
