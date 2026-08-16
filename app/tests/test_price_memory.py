from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.bootstrap import build_world, new_session
from app.database.memory import FUJI80, LI_BOSS
from app.entity.memory import PriceMemoryRecord


def test_missing_price_stays_tbd_and_does_not_block():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件")
    assert session.draft.lines[0].price.source == "tbd"
    assert any(i.code == "price_tbd" and i.block_level == "notice" for i in result.verdict.issues)
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True


def test_explicit_price_is_recorded_as_quote_not_from_order_confirm():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果按3块")
    assert session.draft.lines[0].price.source == "explicit"
    assert session.draft.lines[0].price.unit_price == Decimal("3")
    quotes = [p for p in catalog.prices.snapshot() if p.price_type == "last_quote"]
    assert quotes
    assert quotes[0].unit_price == Decimal("3")
    assert "price_explicit" in result.verdict.reasons


def test_last_deal_is_not_applied_silently():
    runner, _events, catalog = build_world()
    catalog.prices.put(
        PriceMemoryRecord(
            price_type="last_deal",
            customer_id=LI_BOSS,
            product_id=FUJI80,
            unit_price=Decimal("2.5"),
            price_uom="斤",
            valid_until=datetime.now(UTC) + timedelta(days=7),
        )
    )
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    assert session.draft.lines[0].price.source == "tbd"
    expired = PriceMemoryRecord(
        price_type="market_today",
        customer_id=None,
        product_id=FUJI80,
        unit_price=Decimal("9"),
        price_uom="斤",
        valid_until=datetime.now(UTC) - timedelta(days=1),
    )
    catalog.prices.put(expired)
    session2 = new_session()
    runner.handle(session2, "开李老板的单")
    runner.handle(session2, "苹果60件")
    assert session2.draft.lines[0].price.source == "tbd"
    assert session2.draft.lines[0].price.unit_price != Decimal("9")
