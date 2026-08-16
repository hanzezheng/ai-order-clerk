from app.bootstrap import build_world, new_session
from app.database.memory import APPLE, FUJI80, GOLDEN
from app.services.product_resolver import ProductResolver


def test_multi_sku_same_name_does_not_auto_pick():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开王老板的单")
    runner.handle(session, "王记水果店")
    result = runner.handle(session, "苹果60件")
    line = session.draft.lines[0]
    assert line.product_sku_id is None
    assert line.mention.matched_node is not None
    assert line.mention.matched_node.id == APPLE
    assert len(line.mention.candidates) >= 2
    assert any(i.code == "product_ambiguous" for i in result.verdict.issues)


def test_profile_default_fills_after_resolver():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    result = runner.handle(session, "苹果60件")
    line = session.draft.lines[0]
    assert line.product_sku_id == FUJI80
    assert line.mention.filled_from == "profile"
    assert "profile_default_sku" in result.verdict.reasons


def test_resolver_uses_alias_memory_but_does_not_write():
    runner, _events, catalog = build_world()
    before = list(catalog.aliases.snapshot())
    resolver = ProductResolver(catalog, catalog.aliases)
    catalog.aliases.put("金边儿", GOLDEN)
    mention = resolver.resolve("金边儿")
    assert mention.matched_node is not None
    assert mention.matched_node.id == GOLDEN
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "加两个金边榴莲")
    after = catalog.aliases.snapshot()
    assert before == [item for item in after if item[0] != "金边儿"]
    assert ("金边儿", GOLDEN) in after
