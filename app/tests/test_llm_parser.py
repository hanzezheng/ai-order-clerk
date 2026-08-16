import json
from inspect import signature
from pathlib import Path

from pydantic import ValidationError

from app.agent.evaluation import ParserEvaluationRecord, ParserEvaluationReport
from app.agent.llm_client import FakeLlmClient, UnconfiguredLlmClient, client_from_env
from app.agent.llm_convert import llm_turn_to_domain
from app.agent.llm_parser import LLMTurnParser
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
    assert parsed.fallback_reason
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
    from app.agent.prompts import PARSER_SYSTEM_PROMPT

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
