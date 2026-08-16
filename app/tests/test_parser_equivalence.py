from __future__ import annotations

from app.agent.llm_client import FakeLlmClient, UnconfiguredLlmClient
from app.agent.llm_parser import LLMTurnParser
from app.agent.turn_parser import RuleTurnParser
from app.bootstrap import assemble_world, build_app_world, memory_bundle, new_session
from app.database.uow import InMemoryUnitOfWork


_SCRIPTS = [
    ["开李老板的单", "苹果60件", "好了"],
    ["开李老板的单", "苹果60件梨60件加两个金边榴莲不对榴莲改三个", "好了"],
    ["开李老板的单", "苹果按3块", "好了"],
    ["开王老板的单", "王记水果店", "梨60件", "好了"],
]


def _rule_payload(text: str) -> dict:
    parsed = RuleTurnParser().parse(text)
    return {
        "acts": [
            {
                "type": act.type,
                "slots": dict(act.slots),
                "span": act.span,
            }
            for act in parsed.acts
        ]
    }


def _snapshot(session) -> dict:
    return {
        "status": session.draft.status,
        "customer_id": session.draft.customer.id if session.draft.customer else None,
        "customer_name": session.draft.customer.name if session.draft.customer else None,
        "lines": [
            (
                line.product_sku_id,
                str(line.qty.value),
                line.qty.uom,
                line.price.source,
                str(line.price.unit_price) if line.price.unit_price is not None else None,
            )
            for line in session.draft.lines
        ],
    }


def _run(parser, lines: list[str]):
    uow = InMemoryUnitOfWork()
    world = assemble_world(memory_bundle(uow), parser, uow=uow)
    session = new_session()
    last = None
    for text in lines:
        last = world.runner.handle(session, text)
        session = last.session
    assert last is not None
    return last, _snapshot(session)


def test_unconfigured_default_parser_is_llm_shell(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    world = build_app_world()
    parser = world.runner._parser
    assert isinstance(parser, LLMTurnParser)
    assert isinstance(parser._fallback, RuleTurnParser)
    assert parser._client.available() is False


def test_unconfigured_parse_matches_rule_and_is_not_failure_fallback():
    rule = RuleTurnParser()
    llm = LLMTurnParser(client=UnconfiguredLlmClient(), fallback=RuleTurnParser())
    text = "苹果60件梨60件加两个金边榴莲不对榴莲改三个"
    left = rule.parse(text)
    right = llm.parse(text)
    assert right.parser_name == "rule"
    assert right.fallback is False
    assert right.fallback_reason == "llm_unconfigured"
    assert [act.type for act in left.acts] == [act.type for act in right.acts]
    assert [act.slots for act in left.acts] == [act.slots for act in right.acts]


def test_unconfigured_default_world_matches_explicit_rule_world(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    rule_world_result = _run(RuleTurnParser(), _SCRIPTS[0])
    default_world = build_app_world()
    session = new_session()
    last = None
    for text in _SCRIPTS[0]:
        last = default_world.runner.handle(session, text)
        session = last.session
    assert last is not None
    assert last.verdict.confirm_ok is True
    assert _snapshot(session) == rule_world_result[1]


def test_rule_parser_and_llm_parser_are_business_equivalent():
    for lines in _SCRIPTS:
        responses = {text: _rule_payload(text) for text in lines}
        llm = LLMTurnParser(client=FakeLlmClient(responses=responses), fallback=RuleTurnParser())
        rule_result, rule_snap = _run(RuleTurnParser(), lines)
        llm_result, llm_snap = _run(llm, lines)
        assert [act.type for act in rule_result.acts] == [act.type for act in llm_result.acts]
        assert rule_result.verdict.confirm_ok == llm_result.verdict.confirm_ok
        assert rule_snap == llm_snap
