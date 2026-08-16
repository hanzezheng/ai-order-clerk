from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.bootstrap import build_world, new_session
from app.database.memory import FUJI80, LI_BOSS
from app.entity.context import BusinessContext
from app.entity.memory import PriceMemoryRecord
from app.services.context_loader import ContextLoader


def _put_last_deal(catalog, *, expired: bool = False) -> None:
    until = datetime.now(UTC) - timedelta(days=1) if expired else datetime.now(UTC) + timedelta(days=7)
    catalog.prices.put(
        PriceMemoryRecord(
            price_type="last_deal",
            customer_id=LI_BOSS,
            product_id=FUJI80,
            unit_price=Decimal("2.5"),
            price_uom="斤",
            valid_until=until,
        )
    )


def test_unbound_customer_loads_empty_context():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开王老板的单")
    loader = ContextLoader(catalog, catalog.prices)
    ctx = loader.load(session)
    assert ctx.customer_id is None
    assert ctx.price_facts == []
    assert ctx.profile_defaults == []


def test_unbound_turn_has_no_price_notices():
    runner, _events, catalog = build_world()
    _put_last_deal(catalog)
    session = new_session()
    first = runner.handle(session, "开王老板的单")
    second = runner.handle(session, "苹果60件")
    for result in (first, second):
        codes = [i.code for i in result.verdict.issues if i.block_level == "notice"]
        assert "last_deal_available_not_applied" not in codes
        assert "2.5" not in result.reply_text
        if result.reply_plan:
            assert result.reply_plan.notices == []


def test_last_deal_becomes_notice_without_changing_price():
    runner, _events, catalog = build_world()
    _put_last_deal(catalog)
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件")
    assert session.draft.lines[0].price.source == "tbd"
    assert session.draft.lines[0].price.unit_price != Decimal("2.5")
    assert any(i.code == "last_deal_available_not_applied" and i.block_level == "notice" for i in result.verdict.issues)
    notice = next(n for n in result.reply_plan.notices if n.code == "last_deal_available_not_applied")
    assert notice.severity
    assert any(ref.kind == "price" and ref.text == "2.5" for ref in notice.source_refs)
    assert "2.5" in result.reply_text
    assert "未采用成交价" in result.reply_text


def test_ack_omits_last_deal_notice():
    runner, _events, catalog = build_world()
    _put_last_deal(catalog)
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件", expect_more=True)
    assert result.verdict.reply_mode == "ack"
    assert result.reply_plan.reply_scope == "changed_only"
    assert result.reply_plan.notices == []
    assert "未采用成交价" not in result.reply_text
    assert session.draft.lines[0].price.source == "tbd"


def test_expired_deal_notice_does_not_apply_price():
    runner, _events, catalog = build_world()
    _put_last_deal(catalog, expired=True)
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件")
    assert session.draft.lines[0].price.source == "tbd"
    assert any(i.code == "price_memory_expired" for i in result.verdict.issues)
    assert "成交价已过期" in result.reply_text
    assert session.draft.lines[0].price.unit_price != Decimal("2.5")


def test_market_today_is_hint_not_order_price():
    runner, _events, catalog = build_world()
    catalog.prices.put(
        PriceMemoryRecord(
            price_type="market_today",
            customer_id=None,
            product_id=FUJI80,
            unit_price=Decimal("9"),
            price_uom="斤",
            valid_until=datetime.now(UTC) + timedelta(hours=8),
        )
    )
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件")
    assert session.draft.lines[0].price.source == "tbd"
    assert session.draft.lines[0].price.unit_price != Decimal("9")
    assert any(i.code == "market_hint_not_applied" for i in result.verdict.issues)
    assert "今日行情未写入" in result.reply_text
    assert "9" in result.reply_text


def test_reply_notice_has_no_final_chinese():
    runner, _events, catalog = build_world()
    _put_last_deal(catalog)
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件")
    notice = next(n for n in result.reply_plan.notices if n.code == "last_deal_available_not_applied")
    blob = notice.model_dump()
    assert "text" not in blob
    assert "message" not in blob
    assert "未采用成交价" not in str(blob)


def test_empty_context_is_not_full_profile():
    ctx = BusinessContext()
    assert list(BusinessContext.model_fields) == ["customer_id", "profile_defaults", "price_facts"]
