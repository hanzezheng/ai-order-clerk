import json
from inspect import signature
from pathlib import Path

from pydantic import ValidationError

from app.agent.evaluation import ParserEvaluationRecord, ParserEvaluationReport
from app.agent.llm_client import FakeLlmClient, UnconfiguredLlmClient, client_from_env
from app.agent.llm_convert import llm_turn_to_domain
from app.agent.llm_parser import LLMTurnParser, parse_llm_output
from app.agent.llm_schema import LlmTurnParse
from app.agent.parser import TurnParser
from app.agent.turn_parser import RuleTurnParser
from app.bootstrap import build_world, new_session


def _llm_parser(payload, *, error: Exception | None = None) -> LLMTurnParser:
    return LLMTurnParser(
        client=FakeLlmClient(default=payload, error=error),
        fallback=RuleTurnParser(),
    )


def test_parse_signature_matches_protocol():
    assert list(signature(LLMTurnParser.parse).parameters) == ["self", "text"]
    assert list(signature(RuleTurnParser.parse).parameters) == ["self", "text"]


def test_rule_and_llm_parsers_are_interchangeable():
    rule: TurnParser = RuleTurnParser()
    llm: TurnParser = _llm_parser({"acts": []})
    for parser in (rule, llm):
        parsed = parser.parse("苹果60件")
        assert parsed.raw_text == "苹果60件"
        assert parsed.acts


def test_open_order_and_apple_line():
    parsed = _llm_parser(
        {
            "acts": [
                {"type": "start_order", "slots": {"customer_mention": "王老板"}},
                {"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}},
            ]
        }
    ).parse("开王老板的单苹果60件")
    assert [a.type for a in parsed.acts] == ["start_order", "set_line"]
    assert parsed.acts[0].slots["customer_mention"] == "王老板"
    assert parsed.acts[1].slots["product_mention"] == "苹果"
    assert parsed.acts[1].slots["qty"] == 60
    assert parsed.parser_name == "llm"
    assert parsed.fallback is False
    assert parsed.fallback_reason is None
    assert "sku_id" not in parsed.acts[1].slots
    assert "product_id" not in parsed.acts[1].slots


def test_burst_three_speech_acts():
    parsed = _llm_parser(
        {
            "acts": [
                {"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}},
                {"type": "set_line", "slots": {"product_mention": "梨", "qty": 60, "uom": "件"}},
                {"type": "add_line", "slots": {"product_mention": "金边榴莲", "qty": 2, "uom": "个"}},
            ]
        }
    ).parse("苹果60件梨60件加两个金边榴莲")
    assert len(parsed.acts) == 3
    assert [a.type for a in parsed.acts] == ["set_line", "set_line", "add_line"]
    assert [a.slots["product_mention"] for a in parsed.acts] == ["苹果", "梨", "金边榴莲"]


def test_anaphora_stays_unknown_without_guessing_sku():
    parsed = _llm_parser(
        {
            "acts": [
                {"type": "unknown", "slots": {"product_mention": "以前那个"}},
            ]
        }
    ).parse("还是以前那个")
    assert len(parsed.acts) == 1
    assert parsed.acts[0].type == "unknown"
    assert parsed.acts[0].slots["product_mention"] == "以前那个"
    blob = str(parsed.acts[0].slots)
    assert "红富士" not in blob
    assert "sku" not in blob.lower()
    assert "product_id" not in parsed.acts[0].slots


def test_invalid_json_falls_back_to_rule_parser():
    parsed = LLMTurnParser(
        client=FakeLlmClient(default="{not-json"),
        fallback=RuleTurnParser(),
    ).parse("苹果60件")
    assert parsed.parser_name == "rule"
    assert parsed.fallback is True
    assert parsed.fallback_reason == "invalid_json"
    assert parsed.acts[0].type == "set_line"
    assert parsed.acts[0].slots["product_mention"] == "苹果"
    assert parsed.acts[0].slots["qty"] == 60


def test_schema_violation_falls_back_with_reason():
    parsed = _llm_parser(
        {
            "acts": [
                {
                    "type": "set_line",
                    "slots": {"product_mention": "苹果", "qty": 60, "sku_id": "fuji-80"},
                }
            ]
        }
    ).parse("苹果60件")
    assert parsed.fallback is True
    assert parsed.parser_name == "rule"
    assert parsed.fallback_reason == "schema_validation_error"
    assert parsed.acts[0].type == "set_line"


def test_client_error_falls_back_with_reason():
    parsed = _llm_parser({"acts": []}, error=RuntimeError("api down")).parse("苹果60件")
    assert parsed.fallback is True
    assert parsed.parser_name == "rule"
    assert parsed.fallback_reason == "client_error"


def test_runner_accepts_llm_parser():
    parser = _llm_parser(
        {
            "acts": [
                {"type": "start_order", "slots": {"customer_mention": "李老板"}},
                {"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}},
            ]
        }
    )
    runner, _events, _catalog = build_world(parser=parser)
    session = new_session()
    result = runner.handle(session, "开李老板的单苹果60件")
    assert [a.type for a in result.acts] == ["start_order", "set_line"]
    assert session.draft.customer is not None
    assert session.draft.lines


def test_llm_schema_is_not_domain_speech_act():
    llm = LlmTurnParse.model_validate(
        {"acts": [{"type": "unknown", "slots": {"product_mention": "以前那个"}}]}
    )
    domain = llm_turn_to_domain(llm, raw_text="还是以前那个")
    assert type(llm.acts[0]).__name__ == "LlmSpeechAct"
    assert type(domain.acts[0]).__name__ == "SpeechAct"
    assert domain.acts[0].type == "unknown"


def test_llm_schema_rejects_business_ids():
    try:
        LlmTurnParse.model_validate(
            {"acts": [{"type": "set_line", "slots": {"product_mention": "苹果", "sku_id": "x"}}]}
        )
    except ValidationError:
        return
    raise AssertionError("sku_id must not be accepted by LLM schema")


def test_parser_evaluation_structures_are_unscored():
    report = ParserEvaluationReport(
        records=[
            ParserEvaluationRecord(
                case_id="anaphora",
                text="还是以前那个",
                parser_name="llm",
                predicted_acts=[],
                expected_acts=[],
            )
        ]
    )
    assert report.scored is False
    assert report.score is None
    assert report.records[0].match_count is None


def test_client_from_env_without_key_is_unconfigured(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    client = client_from_env()
    assert client.available() is False


def test_unconfigured_client_skips_llm_without_failure_flag():
    parsed = LLMTurnParser(client=UnconfiguredLlmClient(), fallback=RuleTurnParser()).parse("苹果60件")
    assert parsed.parser_name == "rule"
    assert parsed.fallback is False
    assert parsed.fallback_reason == "llm_unconfigured"
    assert parsed.acts[0].type == "set_line"


def test_spec_mention_stays_language_slot_and_is_not_mapped_to_sku():
    llm = LlmTurnParse.model_validate(
        {"acts": [{"type": "refine_spec", "slots": {"spec_mention": "八零果"}}]}
    )
    domain = llm_turn_to_domain(llm, raw_text="八零果")
    assert domain.acts[0].type == "refine_spec"
    assert domain.acts[0].slots == {"spec_mention": "八零果"}
    assert "product_mention" not in domain.acts[0].slots
    assert "sku_id" not in domain.acts[0].slots
    assert "product_id" not in domain.acts[0].slots


def test_prompt_has_no_catalog_or_price_knowledge():
    from typing import get_args

    from app.agent.llm_schema import LlmActType
    from app.agent.prompts import PARSER_PROMPT_ID, PARSER_PROMPTS, PARSER_SYSTEM_PROMPT

    assert PARSER_PROMPT_ID == "parser.v4"
    assert "parser.v3" in PARSER_PROMPTS

    for needle in (
        "红富士80",
        "烟台箱装",
        "李记果行",
        "王强水果店",
        "皇冠梨",
        "product_defaults",
        "last_deal",
        "Catalog",
    ):
        assert needle not in PARSER_SYSTEM_PROMPT

    for act_type in get_args(LlmActType):
        assert act_type in PARSER_SYSTEM_PROMPT
    assert "add_item" in PARSER_SYSTEM_PROMPT


def test_qwen_array_with_flat_slots_normalizes_without_fallback():
    parsed = _llm_parser(
        '```json\n[\n  {\n    "type": "start_order",\n    "customer_mention": "王老板"\n  }\n]\n```'
    ).parse("开王老板的单")
    assert parsed.fallback is False
    assert parsed.parser_name == "llm"
    assert parsed.acts[0].type == "start_order"
    assert parsed.acts[0].slots["customer_mention"] == "王老板"


def test_flat_language_slots_lift_into_slots():
    parsed = parse_llm_output(
        [{"type": "refine_spec", "spec_mention": "八零果"}]
    )
    assert parsed.acts[0].type == "refine_spec"
    assert parsed.acts[0].slots.spec_mention == "八零果"


def test_top_level_sku_id_still_rejected_after_normalize():
    try:
        parse_llm_output(
            [{"type": "set_line", "product_mention": "苹果", "qty": 60, "sku_id": "fuji-80"}]
        )
    except ValidationError:
        return
    raise AssertionError("sku_id must still fail after shape normalization")


def test_customer_id_still_rejected_after_normalize():
    try:
        parse_llm_output(
            {"acts": [{"type": "start_order", "slots": {"customer_mention": "老王", "customer_id": "x"}}]}
        )
    except ValidationError:
        return
    raise AssertionError("customer_id must still fail after shape normalization")


def test_unknown_business_field_still_rejected():
    try:
        parse_llm_output([{"type": "set_line", "product_mention": "苹果", "resolved_sku": "x"}])
    except ValidationError:
        return
    raise AssertionError("unknown business field must still fail")


def test_json_fences_are_stripped_before_schema():
    parsed = _llm_parser('```json\n{"acts": [{"type": "confirm_order", "slots": {}}]}\n```').parse("好了")
    assert parsed.fallback is False
    assert parsed.acts[0].type == "confirm_order"


def test_dataset_has_at_least_20_language_cases():
    path = Path(__file__).resolve().parents[2] / "docs/dataset/sales_parser_cases.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(payload["cases"]) >= 35
    stall = [case for case in payload["cases"] if case.get("tag") == "stall_oral"]
    assert len(stall) >= 12
    for case in payload["cases"]:
        blob = json.dumps(case["expected_acts"], ensure_ascii=False)
        assert "sku_id" not in blob
        assert "product_id" not in blob
        assert "customer_id" not in blob
        assert "红富士80" not in blob
        assert "王强水果店" not in blob


def test_add_item_aliases_to_add_line_without_fallback():
    parsed = _llm_parser(
        {
            "acts": [
                {"type": "start_order", "slots": {"customer_mention": "老王"}},
                {
                    "type": "add_item",
                    "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"},
                },
            ]
        }
    ).parse("开老王的单苹果60件")
    assert parsed.fallback is False
    assert parsed.parser_name == "llm"
    assert [a.type for a in parsed.acts] == ["start_order", "add_line"]
    assert parsed.acts[1].slots["product_mention"] == "苹果"
    assert parsed.acts[1].slots["qty"] == 60


def test_set_spec_aliases_to_refine_spec():
    parsed = parse_llm_output(
        {"acts": [{"type": "set_spec", "slots": {"spec_mention": "八零果"}}]}
    )
    assert parsed.acts[0].type == "refine_spec"
    assert parsed.acts[0].slots.spec_mention == "八零果"


def test_invented_type_still_falls_back():
    parsed = _llm_parser(
        {"acts": [{"type": "explode_order", "slots": {"customer_mention": "老王"}}]}
    ).parse("开老王的单")
    assert parsed.fallback is True
    assert parsed.parser_name == "rule"
    assert parsed.fallback_reason == "schema_validation_error"


def test_done_is_not_aliased_to_confirm():
    parsed = _llm_parser({"acts": [{"type": "done", "slots": {}}]}).parse("好了")
    assert parsed.fallback is True
    assert parsed.acts[0].type == "confirm_order"
    assert parsed.parser_name == "rule"


def test_two_ge_fills_uom_without_inventing_sku():
    parsed = _llm_parser(
        {"acts": [{"type": "add_line", "slots": {"product_mention": "金边榴莲", "qty": 2}}]}
    ).parse("加两个金边榴莲")
    assert parsed.fallback is False
    assert parsed.acts[0].type == "add_line"
    assert parsed.acts[0].slots["qty"] == 2
    assert parsed.acts[0].slots["uom"] == "个"
    assert "sku_id" not in parsed.acts[0].slots


def test_bare_add_qty_becomes_set_qty_add_mode():
    parsed = _llm_parser(
        {"acts": [{"type": "add_line", "slots": {"qty": 20, "uom": "件"}}]}
    ).parse("再加20件")
    assert parsed.fallback is False
    assert parsed.acts[0].type == "set_qty"
    assert parsed.acts[0].slots["qty"] == 20
    assert parsed.acts[0].slots["uom"] == "件"
    assert parsed.acts[0].slots["mode"] == "add"
    assert "product_mention" not in parsed.acts[0].slots


def test_bare_that_apple_is_unknown_not_set_line():
    parsed = _llm_parser(
        {"acts": [{"type": "set_line", "slots": {"product_mention": "那个苹果"}}]}
    ).parse("那个苹果")
    assert parsed.fallback is False
    assert parsed.acts[0].type == "unknown"
    assert parsed.acts[0].slots["product_mention"] == "那个苹果"
    assert "uom" not in parsed.acts[0].slots


def test_anaphora_mention_moves_to_product_mention():
    parsed = _llm_parser(
        {
            "acts": [
                {
                    "type": "set_qty",
                    "slots": {"qty": 80, "uom": "件", "mention": "刚才那个"},
                }
            ]
        }
    ).parse("刚才那个改80件")
    assert parsed.fallback is False
    assert parsed.acts[0].type == "set_qty"
    assert parsed.acts[0].slots["product_mention"] == "刚才那个"
    assert "mention" not in parsed.acts[0].slots


def test_remove_that_uses_product_mention_not_mention():
    parsed = _llm_parser(
        {"acts": [{"type": "remove_line", "slots": {"mention": "那个"}}]}
    ).parse("那个不要了")
    assert parsed.fallback is False
    assert parsed.acts[0].type == "remove_line"
    assert parsed.acts[0].slots["product_mention"] == "那个"
    assert "mention" not in parsed.acts[0].slots


def test_clarify_keeps_mention_slot():
    parsed = _llm_parser(
        {"acts": [{"type": "clarify", "slots": {"mention": "3号档那个"}}]}
    ).parse("3号档那个")
    assert parsed.fallback is False
    assert parsed.acts[0].type == "clarify"
    assert parsed.acts[0].slots["mention"] == "3号档那个"
    assert "product_mention" not in parsed.acts[0].slots


def test_give_me_pear_stays_add_line():
    parsed = _llm_parser(
        {"acts": [{"type": "add_line", "slots": {"product_mention": "梨"}}]}
    ).parse("给我来点梨")
    assert parsed.acts[0].type == "add_line"
    assert parsed.acts[0].slots["product_mention"] == "梨"


def test_anaphoric_add_with_qty_stays_add_line():
    parsed = _llm_parser(
        {"acts": [{"type": "add_line", "slots": {"product_mention": "那个红的", "qty": 2, "uom": "件"}}]}
    ).parse("那个红的再来两件")
    assert parsed.acts[0].type == "add_line"
    assert parsed.acts[0].slots["product_mention"] == "那个红的"
    assert parsed.acts[0].slots["qty"] == 2
