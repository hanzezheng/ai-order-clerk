from uuid import uuid4

from app.bootstrap import build_world, new_session
from app.database.memory import APPLE, FUJI80, GREEN_SKU, LI_BOSS
from app.entity.events import ORDER_CONFIRMED, PREFERENCE_ADJUSTED
from app.entity.memory import MemoryCandidate
from app.entity.speech import SpeechAct
from app.memory.evidence import EvidenceStore
from app.memory.policy import MemoryPolicy
from app.policy.decision import DecisionPolicy
from app.services.catalog_service import OntologyService
from app.services.product_resolver import ProductResolver

_ADJUST_FIELDS = {"customer_id", "node_id", "from_sku_id", "to_sku_id", "order_id"}


def _confirm_li(runner, product_text: str):
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, product_text)
    done = runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    return session


def _adjustments(events, order_id):
    return [
        e
        for e in events.events
        if e.event_type == PREFERENCE_ADJUSTED and e.aggregate_id == order_id
    ]


def test_session_suppresses_profile_default_without_writing_memory():
    runner, events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    assert session.draft.lines[0].product_sku_id == FUJI80
    runner.handle(session, "青苹果60件")
    assert session.draft.lines[0].product_sku_id == GREEN_SKU
    assert APPLE in session.suppressed_default_node_ids
    profile = catalog.get_profile(LI_BOSS)
    assert profile is not None
    assert profile.product_defaults[str(APPLE)] == FUJI80
    assert _adjustments(events, session.draft.order_id) == []

    ontology = OntologyService(catalog)
    filled = DecisionPolicy(ontology).fill_sku(
        ProductResolver(catalog, catalog.aliases).resolve("苹果"),
        profile,
        suppressed_node_ids=session.suppressed_default_node_ids,
    )
    assert filled.filled_from != "profile"
    assert filled.resolved_sku is None


def test_unconfirmed_correction_does_not_emit_preference_adjusted():
    runner, events, catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    runner.handle(session, "苹果60件")
    runner.handle(session, "青苹果60件")
    assert session.draft.status != "confirmed"
    assert _adjustments(events, session.draft.order_id) == []
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == FUJI80


def test_one_green_confirm_emits_structured_preference_adjusted_without_user_text():
    runner, events, catalog = build_world()
    session = _confirm_li(runner, "青苹果60件")
    adj = _adjustments(events, session.draft.order_id)
    assert len(adj) == 1
    payload = adj[0].payload
    assert set(payload) == _ADJUST_FIELDS
    assert "user_text" not in payload
    assert payload["customer_id"] == str(LI_BOSS)
    assert payload["node_id"] == str(APPLE)
    assert payload["from_sku_id"] == str(FUJI80)
    assert payload["to_sku_id"] == str(GREEN_SKU)
    assert payload["order_id"] == str(session.draft.order_id)
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == FUJI80


def test_confirming_archive_default_does_not_emit_preference_adjusted():
    runner, events, catalog = build_world()
    session = _confirm_li(runner, "苹果60件")
    assert session.draft.lines[0].product_sku_id == FUJI80
    assert any(e.event_type == ORDER_CONFIRMED and e.aggregate_id == session.draft.order_id for e in events.events)
    assert _adjustments(events, session.draft.order_id) == []
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == FUJI80


def test_two_green_confirms_keep_fuji_default_third_upgrades():
    runner, _events, catalog = build_world()
    _confirm_li(runner, "青苹果60件")
    _confirm_li(runner, "青苹果60件")
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == FUJI80
    _confirm_li(runner, "青苹果60件")
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == GREEN_SKU


def test_conflict_recovery_old_default_new_preference_then_old_default():
    runner, _events, catalog = build_world()
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == FUJI80
    for _ in range(3):
        _confirm_li(runner, "青苹果60件")
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == GREEN_SKU
    _confirm_li(runner, "红富士80件")
    _confirm_li(runner, "红富士80件")
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == GREEN_SKU
    _confirm_li(runner, "红富士80件")
    assert catalog.get_profile(LI_BOSS).product_defaults[str(APPLE)] == FUJI80


def test_preference_adjusted_candidate_never_writes_product_default():
    decision = MemoryPolicy().decide(
        MemoryCandidate(
            kind="product_default",
            source_event=PREFERENCE_ADJUSTED,
            customer_id=LI_BOSS,
            node_id=APPLE,
            sku_id=GREEN_SKU,
            evidence_count=99,
            reason="should_not_write",
        )
    )
    assert decision.write is False
    assert "preference_adjusted" in decision.reason


def test_extractor_ignores_speech_act_and_user_text():
    runner, _events, _catalog = build_world()
    session = new_session()
    runner.handle(session, "开李老板的单")
    act = SpeechAct(type="set_line", slots={"product_mention": "青苹果", "qty": 60}, span="今天换青苹果")
    assert runner._memory_extractor.extract(act, session) == []


def test_evidence_delta_keeps_non_negative_net_and_preserves_signed_counts():
    store = EvidenceStore()
    customer_id = uuid4()
    node_id = uuid4()
    sku_id = uuid4()
    missing = store.adjust(
        customer_id=customer_id,
        kind="product_default",
        node_id=node_id,
        sku_id=sku_id,
        delta=-1,
    )
    assert missing.count == 0
    assert missing.positive_count == 0
    assert missing.negative_count == 1
    store.observe(customer_id=customer_id, kind="product_default", node_id=node_id, sku_id=sku_id)
    store.observe(customer_id=customer_id, kind="product_default", node_id=node_id, sku_id=sku_id)
    store.observe(customer_id=customer_id, kind="product_default", node_id=node_id, sku_id=sku_id)
    record = store.adjust(
        customer_id=customer_id,
        kind="product_default",
        node_id=node_id,
        sku_id=sku_id,
        delta=-1,
    )
    assert record.positive_count == 3
    assert record.negative_count == 2
    assert record.count == 1
    assert record.status == "pending"
