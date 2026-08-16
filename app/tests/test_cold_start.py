from app.bootstrap import build_world, new_session
from app.database.memory import PEAR, PEAR_SKU
from app.policy.decision import DecisionPolicy
from app.services.catalog_service import OntologyService
from app.services.product_resolver import ProductResolver


def _issues(result, code: str | None = None):
    issues = result.verdict.issues
    if code:
        return [i for i in issues if i.code == code]
    return issues


def _zhao_customer(catalog, mention: str = "赵老板"):
    return [
        c
        for c in catalog.list_customers()
        if mention in {c.display_name, c.legal_name, *c.aliases}
    ]


def test_unknown_customer_asks_stall_and_does_not_create():
    runner, _events, catalog = build_world()
    before = {c.id for c in catalog.list_customers()}
    session = new_session()
    result = runner.handle(session, "开赵老板的单")
    assert session.draft.customer is None
    assert _issues(result, "customer_unknown")
    assert result.verdict.confirm_ok is False
    assert "赵老板" in result.reply_text
    assert _zhao_customer(catalog) == []
    assert {c.id for c in catalog.list_customers()} == before


def test_unknown_customer_creates_candidate_with_stall():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开赵老板的单")
    result = runner.handle(session, "3号档")
    assert session.draft.customer is not None
    created = _zhao_customer(catalog)
    assert len(created) == 1
    assert created[0].stall_no == "3"
    assert created[0].status == "candidate"
    assert session.draft.customer.id == created[0].id
    profile = catalog.get_profile(created[0].id)
    assert profile is not None
    assert profile.product_defaults == {}
    assert result.session.draft.customer.id == created[0].id


def test_candidate_customer_is_not_silently_rebound():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开赵老板的单")
    runner.handle(session, "3号档")
    other = new_session()
    result = runner.handle(other, "开赵老板的单")
    assert other.draft.customer is None
    assert _issues(result, "customer_unknown")
    zhao = _zhao_customer(catalog)[0]
    assert zhao.status == "candidate"
    runner.handle(other, "3号档")
    assert other.draft.customer is not None
    assert other.draft.customer.id == zhao.id
    assert len(_zhao_customer(catalog)) == 1


def test_same_alias_and_stall_does_not_duplicate():
    runner, _events, catalog = build_world()
    first = new_session()
    runner.handle(first, "开赵老板的单")
    runner.handle(first, "3号档")
    second = new_session()
    runner.handle(second, "开赵老板的单")
    runner.handle(second, "东市场3号档")
    assert len(_zhao_customer(catalog)) == 1


def test_wrong_stall_does_not_pollute_existing_candidate():
    runner, _events, catalog = build_world()
    first = new_session()
    runner.handle(first, "开赵老板的单")
    runner.handle(first, "3号档")
    first_id = first.draft.customer.id
    second = new_session()
    runner.handle(second, "开赵老板的单")
    runner.handle(second, "5号档")
    found = _zhao_customer(catalog)
    assert len(found) == 2
    assert {c.stall_no for c in found} == {"3", "5"}
    assert second.draft.customer.id != first_id


def test_first_confirm_promotes_candidate_to_observed():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开赵老板的单")
    runner.handle(session, "3号档")
    runner.handle(session, "梨60件")
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    zhao = _zhao_customer(catalog)[0]
    assert zhao.status == "observed"
    assert zhao.confirm_count == 1
    next_session = new_session()
    opened = runner.handle(next_session, "开赵老板的单")
    assert next_session.draft.customer is not None
    assert next_session.draft.customer.id == zhao.id
    assert "customer_unique" in opened.verdict.reasons


def test_three_confirms_promote_to_trusted():
    runner, _events, catalog = build_world()

    def _one_pear():
        session = new_session()
        runner.handle(session, "开赵老板的单")
        if session.draft.customer is None:
            runner.handle(session, "3号档")
        runner.handle(session, "梨60件")
        done = runner.handle(session, "好了")
        assert done.verdict.confirm_ok is True

    _one_pear()
    assert _zhao_customer(catalog)[0].status == "observed"
    _one_pear()
    assert _zhao_customer(catalog)[0].status == "observed"
    _one_pear()
    zhao = _zhao_customer(catalog)[0]
    assert zhao.status == "trusted"
    assert zhao.confirm_count == 3
    assert catalog.get_profile(zhao.id).product_defaults[str(PEAR)] == PEAR_SKU


def test_first_confirm_does_not_write_product_default():
    runner, _events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开赵老板的单")
    runner.handle(session, "3号档")
    runner.handle(session, "梨60件")
    runner.handle(session, "好了")
    zhao = _zhao_customer(catalog)[0]
    assert catalog.get_profile(zhao.id).product_defaults == {}


def test_unknown_product_records_mention_candidate_without_ontology_change():
    runner, _events, catalog = build_world()
    before_nodes = {n.id for n in catalog.list_nodes()}
    session = new_session()
    runner.handle(session, "开赵老板的单")
    runner.handle(session, "3号档")
    result = runner.handle(session, "紫麒麟60件")
    assert any(m.raw == "紫麒麟" and m.status == "candidate" for m in session.product_mention_candidates)
    assert all(ln.product_sku_id is None for ln in session.draft.lines)
    assert _issues(result, "product_unknown")
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is False
    assert {n.id for n in catalog.list_nodes()} == before_nodes
    assert catalog.aliases.snapshot() == []


def test_fill_sku_does_not_guess_when_mention_unmatched():
    _runner, _events, catalog = build_world()
    mention = ProductResolver(catalog, catalog.aliases).resolve("紫麒麟")
    filled = DecisionPolicy(OntologyService(catalog)).fill_sku(mention, None)
    assert filled.resolved_sku is None
    assert filled.matched_node is None
