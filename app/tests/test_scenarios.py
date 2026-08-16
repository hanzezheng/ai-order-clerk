from __future__ import annotations

from decimal import Decimal

from app.bootstrap import build_world, new_session
from app.database.memory import FUJI80, WANG_QIANG
from app.entity.events import ORDER_CONFIRMED, ORDER_STARTED


def _issues(result, level: str | None = None):
    issues = result.verdict.issues
    if level:
        return [i for i in issues if i.block_level == level]
    return issues


def test_homonym_blocks_without_guessing():
    runner, _events, _catalog = build_world()
    session = new_session()
    result = runner.handle(session, "开王老板的单")
    assert result.session.draft.customer is None
    blocks = _issues(result, "session_block")
    assert blocks
    assert blocks[0].code == "customer_ambiguous"
    names = {opt["name"] for opt in blocks[0].options}
    assert names == {"王强水果店", "王记水果店"}
    assert result.verdict.confirm_ok is False


def test_homonym_continues_after_disambiguation():
    runner, events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开王老板的单")
    result = runner.handle(session, "王强水果店")
    assert session.draft.customer is not None
    assert session.draft.customer.id == WANG_QIANG
    assert session.pending_customer_candidates == []
    assert any(e.event_type == ORDER_STARTED for e in events.events)

    runner.handle(session, "苹果60件")
    runner.handle(session, "梨60件")
    runner.handle(session, "加两个金边榴莲")
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    assert session.draft.status == "confirmed"
    apple = next(ln for ln in session.draft.lines if ln.product_sku_id == FUJI80)
    assert apple.qty.value == Decimal("60")
    pear = next(ln for ln in session.draft.lines if ln.mention.matched_node and "梨" in (ln.mention.matched_node.name + ln.mention.raw))
    assert pear.qty.value == Decimal("60")
    durian = next(ln for ln in session.draft.lines if ln.mention.matched_node and "金边" in ln.mention.matched_node.name or (ln.mention.raw and "榴莲" in ln.mention.raw))
    assert durian.qty.value == Decimal("2")
    assert all(ln.price.source == "tbd" for ln in session.draft.lines)
    assert any(e.event_type == ORDER_CONFIRMED for e in events.events)


def test_qty_correction_on_focus_line():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    result = runner.handle(session, "不对改80件")
    assert len(session.draft.lines) == 1
    assert session.draft.lines[0].qty.value == Decimal("80")
    assert "qty_updated" in result.verdict.reasons


def test_add_more_on_focus_line():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    runner.handle(session, "再加20件")
    assert session.draft.lines[0].qty.value == Decimal("80")


def test_ambiguous_apple_hangs_without_default():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开王老板的单")
    runner.handle(session, "王记水果店")
    result = runner.handle(session, "苹果60件")
    line = session.draft.lines[0]
    assert line.product_sku_id is None
    assert line.mention.matched_node is not None
    assert line.mention.matched_node.name == "苹果"
    assert any(i.code == "product_ambiguous" and i.block_level == "line_hold" for i in result.verdict.issues)
    pear = runner.handle(session, "梨60件")
    assert len(session.draft.lines) == 2
    assert pear.session.draft.lines[1].qty.value == Decimal("60")


def test_missing_price_is_notice_not_block():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件")
    notices = _issues(result, "notice")
    assert any(i.code == "price_tbd" for i in notices)
    assert not _issues(result, "session_block")
    assert session.draft.lines[0].price.source == "tbd"
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True


def test_profile_default_sku_for_apple():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件")
    line = session.draft.lines[0]
    assert line.product_sku_id == FUJI80
    assert line.mention.filled_from == "profile"
    assert "profile_default_sku" in result.verdict.reasons
    assert "红富士" in result.reply_text


def test_single_turn_multi_act_with_durian_correction():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件梨60件加两个金边榴莲不对榴莲改三个")
    types = [a.type for a in result.acts]
    assert types[0] == "set_line"
    assert types[1] == "set_line"
    assert types[2] == "add_line"
    assert types[3] == "set_qty"
    assert len(session.draft.lines) == 3
    apple = next(ln for ln in session.draft.lines if ln.product_sku_id == FUJI80)
    pear = next(ln for ln in session.draft.lines if ln.mention.matched_node and "梨" in ln.mention.matched_node.name)
    durian = next(ln for ln in session.draft.lines if ln.mention.matched_node and "金边" in ln.mention.matched_node.name)
    assert apple.qty.value == Decimal("60")
    assert pear.qty.value == Decimal("60")
    assert durian.qty.value == Decimal("3")


def test_domain_events_are_published_without_consumers():
    runner, events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    runner.handle(session, "好了")
    kinds = [e.event_type for e in events.events]
    assert ORDER_STARTED in kinds
    assert ORDER_CONFIRMED in kinds
    assert events.events[-1].payload.get("prices_incomplete") is True
