from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.llm_client import FakeLlmClient
from app.agent.llm_parser import LLMTurnParser
from app.bootstrap import build_world, new_session
from app.database.memory import APPLE, FUJI80, GREEN_SKU, InMemoryCatalog
from app.entity.catalog import ProductQuery
from app.policy.decision import DecisionPolicy
from app.services.catalog_service import OntologyService
from app.services.product_resolver import ProductResolver
from app.services.product_understanding import ProductUnderstanding, normalize_spec


def _wang_ji(runner):
    session = new_session()
    runner.handle(session, "开王老板的单")
    runner.handle(session, "王记水果店")
    return session


def _slot_parser(utterance: str, act: dict) -> LLMTurnParser:
    return LLMTurnParser(client=FakeLlmClient(responses={utterance: {"acts": [act]}}))


def test_query_has_no_sku_id_and_focus_is_session_only():
    query = ProductUnderstanding().interpret(
        product_mention="苹果",
        spec_mention="八零果",
        focus_node_id=APPLE,
    )
    dumped = query.model_dump()
    assert "sku_id" not in dumped
    assert "product_id" not in dumped
    assert query.attributes == {"size": "80"}
    assert query.lookup_text == "苹果"
    assert query.focus_node_id == APPLE


def test_query_rejects_business_ids():
    with pytest.raises(ValidationError):
        ProductQuery(lookup_text="苹果", sku_id=FUJI80)  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        ProductQuery(lookup_text="苹果", product_id=APPLE)  # type: ignore[call-arg]


def test_compound_mention_strips_spec_for_lookup():
    query = ProductUnderstanding().interpret(product_mention="苹果八十果")
    assert query.lookup_text == "苹果"
    assert query.attributes["size"] == "80"
    assert "sku_id" not in query.model_dump()


def test_normalize_spec_covers_closed_attributes():
    assert normalize_spec("八零果") == {"size": "80"}
    assert normalize_spec("烟台的") == {"origin": "烟台"}
    assert normalize_spec("一级") == {"grade": "一级"}
    assert normalize_spec("统货") == {"grade": "统货"}
    assert normalize_spec("箱装") == {"packing": "箱装"}
    assert normalize_spec("九十果") == {"size": "90"}


def test_unique_spec_promotes_existing_sku_node_without_resolved_sku():
    catalog = InMemoryCatalog()
    mention = ProductResolver(catalog, catalog.aliases).resolve_query(
        ProductUnderstanding().interpret(product_mention="苹果", spec_mention="八零果")
    )
    assert mention.matched_node is not None
    assert mention.matched_node.id == FUJI80
    assert mention.matched_node.level == "sku"
    assert mention.resolved_sku is None
    assert [item.node.id for item in mention.resolution_candidates] == [FUJI80]
    filled = DecisionPolicy(OntologyService(catalog)).fill_sku(mention, None)
    assert filled.resolved_sku is not None
    assert filled.resolved_sku.id == FUJI80


def test_understanding_and_resolver_do_not_write_catalog_or_aliases():
    catalog = InMemoryCatalog()
    before_nodes = {node.id: node.model_dump() for node in catalog.list_nodes()}
    before_aliases = catalog.aliases.snapshot()
    ProductUnderstanding().interpret(product_mention="苹果", spec_mention="八零果")
    ProductResolver(catalog, catalog.aliases).resolve_query(
        ProductUnderstanding().interpret(product_mention="苹果", spec_mention="统货")
    )
    assert catalog.aliases.snapshot() == before_aliases
    assert {node.id: node.model_dump() for node in catalog.list_nodes()} == before_nodes


def test_ambiguous_apple_without_spec_still_has_no_sku():
    runner, _events, _catalog = build_world()
    session = _wang_ji(runner)
    result = runner.handle(session, "苹果60件")
    assert session.draft.lines[0].product_sku_id is None
    assert session.draft.lines[0].mention.matched_node is not None
    assert session.draft.lines[0].mention.matched_node.id == APPLE
    assert any(i.code == "product_ambiguous" for i in result.verdict.issues)
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is False


def test_rule_parser_compound_mention_lands_fuji80():
    runner, _events, _catalog = build_world()
    session = _wang_ji(runner)
    # 规则切词会把「八/八十」当成数量，八零果无法整段留在 product_mention。
    # 规则兜底用非数字规格词；八零果走 LLM spec_mention 槽（见下一用例）。
    runner.handle(session, "苹果烟台60件")
    assert session.draft.lines[0].product_sku_id == FUJI80
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True


def test_llm_slots_apple_plus_spec_on_wang_ji_lands_fuji80():
    parser = _slot_parser(
        "苹果八零果60件",
        {
            "type": "set_line",
            "slots": {
                "product_mention": "苹果",
                "spec_mention": "八零果",
                "qty": 60,
                "uom": "件",
            },
        },
    )
    runner, _events, _catalog = build_world(parser=parser)
    session = _wang_ji(runner)
    runner.handle(session, "苹果八零果60件")
    assert session.draft.lines[0].product_sku_id == FUJI80
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True


def test_refine_spec_on_focus_line_does_not_split():
    runner, _events, _catalog = build_world()
    session = _wang_ji(runner)
    runner.handle(session, "苹果60件")
    line_id = session.draft.lines[0].line_id
    assert session.draft.lines[0].product_sku_id is None
    runner.handle(session, "烟台")
    assert len(session.draft.lines) == 1
    assert session.draft.lines[0].line_id == line_id
    assert session.draft.lines[0].product_sku_id == FUJI80


def test_llm_refine_spec_uses_session_focus_not_sku_slot():
    parser = _slot_parser(
        "八零果",
        {"type": "refine_spec", "slots": {"spec_mention": "八零果"}},
    )
    runner, _events, _catalog = build_world(parser=parser)
    session = _wang_ji(runner)
    runner.handle(session, "苹果60件")
    line_id = session.draft.lines[0].line_id
    runner.handle(session, "八零果")
    assert len(session.draft.lines) == 1
    assert session.draft.lines[0].line_id == line_id
    assert session.draft.lines[0].product_sku_id == FUJI80


def test_unknown_size_does_not_create_sku():
    parser = _slot_parser(
        "苹果九十果60件",
        {
            "type": "set_line",
            "slots": {"product_mention": "苹果", "spec_mention": "九十果", "qty": 60, "uom": "件"},
        },
    )
    runner, _events, catalog = build_world(parser=parser)
    before = {node.id for node in catalog.list_nodes()}
    session = _wang_ji(runner)
    runner.handle(session, "苹果九十果60件")
    assert all(line.product_sku_id is None for line in session.draft.lines)
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is False
    assert {node.id for node in catalog.list_nodes()} == before
    assert catalog.aliases.snapshot() == []


def test_no_substitute_golden_to_unknown():
    runner, _events, catalog = build_world()
    before = {node.id for node in catalog.list_nodes()}
    session = _wang_ji(runner)
    runner.handle(session, "金枕60个")
    assert {node.id for node in catalog.list_nodes()} == before
    assert all(line.product_sku_id is None for line in session.draft.lines)


def test_profile_default_without_spec_unchanged():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    assert session.draft.lines[0].product_sku_id == FUJI80
    assert session.draft.lines[0].mention.filled_from == "profile"


def test_tonghuo_spec_filters_green_sku():
    catalog = InMemoryCatalog()
    mention = ProductResolver(catalog, catalog.aliases).resolve_query(
        ProductUnderstanding().interpret(product_mention="苹果", spec_mention="统货")
    )
    assert mention.matched_node is not None
    assert mention.matched_node.id == GREEN_SKU
    assert mention.resolved_sku is None
