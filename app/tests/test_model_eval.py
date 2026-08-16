from __future__ import annotations

from pathlib import Path

from app.agent.evaluation import (
    LanguageBenchmark,
    ParserEvaluationCase,
    ParserEvaluationRecord,
    ParserEvaluationReport,
    build_eval_parser,
    fake_client_from_cases,
    live_llm_enabled,
    load_parser_cases,
    report_to_json,
)
from app.agent.llm_client import FakeLlmClient, UnconfiguredLlmClient
from app.agent.llm_parser import LLMTurnParser
from app.agent.prompts import PARSER_PROMPT_ID, PARSER_SYSTEM_PROMPT
from app.agent.turn_parser import RuleTurnParser


def test_prompt_id_is_pinned_v5():
    assert PARSER_PROMPT_ID == "parser.v5"
    assert LLMTurnParser.prompt_id == "parser.v5"
    assert "不要选择 SKU" in PARSER_SYSTEM_PROMPT
    assert "不要写记忆" in PARSER_SYSTEM_PROMPT
    assert "不要判断能否确认" in PARSER_SYSTEM_PROMPT
    assert '{"acts": [ ... ]}' in PARSER_SYSTEM_PROMPT or '"acts"' in PARSER_SYSTEM_PROMPT
    assert "禁止与 type 同级摊开" in PARSER_SYSTEM_PROMPT
    assert "禁止 add_item" in PARSER_SYSTEM_PROMPT
    assert "refine_spec" in PARSER_SYSTEM_PROMPT
    assert "再加20件" in PARSER_SYSTEM_PROMPT
    assert "product_mention" in PARSER_SYSTEM_PROMPT
    assert "苹果要烟台八零果" in PARSER_SYSTEM_PROMPT
    assert "槽位只用 spec_mention" not in PARSER_SYSTEM_PROMPT
    assert "line_id" in PARSER_SYSTEM_PROMPT


def test_qwen_flat_array_counts_as_model_pass_not_fallback():
    case = ParserEvaluationCase(
        id="open-wang-boss",
        text="开王老板的单",
        expected_acts=[{"type": "start_order", "slots": {"customer_mention": "王老板"}}],
    )
    parser, capture = build_eval_parser(
        FakeLlmClient(
            default='```json\n[\n  {\n    "type": "start_order",\n    "customer_mention": "王老板"\n  }\n]\n```'
        )
    )
    report = LanguageBenchmark().evaluate(
        [case], parser, mode="live", model="qwen-probe", capture=capture
    )
    row = report.records[0]
    assert row.fallback is False
    assert row.parser_name == "llm"
    assert row.model_pass is True
    assert row.severity == "pass"
    assert report.veto is False


def test_live_requires_explicit_switch_even_with_key(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.delenv("RUN_LIVE_LLM", raising=False)
    assert live_llm_enabled() is False


def test_fake_dataset_is_unscored_and_has_required_report_fields():
    dataset_rev, cases = load_parser_cases()
    parser, capture = build_eval_parser(fake_client_from_cases(cases))
    report = LanguageBenchmark().evaluate(
        cases,
        parser,
        mode="fake",
        model="fake",
        prompt_id=PARSER_PROMPT_ID,
        dataset_rev=dataset_rev,
        capture=capture,
    )
    assert report.scored is False
    assert report.mode == "fake"
    assert report.model == "fake"
    assert report.prompt_id == "parser.v5"
    assert report.veto is False
    assert report.stall_oral_pass_rate == 1.0
    blob = report_to_json(report)
    assert "model" in blob
    assert "prompt_id" in blob
    for row in blob["records"]:
        assert "fallback_reason" in row
        assert "taxonomy" in row
        assert "severity" in row
        assert row["severity"] == "pass"
        assert row["model_pass"] is True


def test_unconfigured_mode_is_not_live_score():
    _, cases = load_parser_cases()
    sample = [case for case in cases if case.id == "apple-60"]
    parser, capture = build_eval_parser(UnconfiguredLlmClient())
    report = LanguageBenchmark().evaluate(sample, parser, mode="unconfigured", model="", capture=capture)
    assert report.scored is False
    assert report.mode == "unconfigured"
    assert report.records[0].parser_name == "rule"
    assert report.records[0].fallback is False
    assert report.records[0].model_pass is False
    assert report.records[0].severity == "pass"


def test_guessed_sku_is_l0_veto():
    case = ParserEvaluationCase(
        id="spec-80",
        tag="stall_oral",
        text="八零果",
        expected_acts=[{"type": "refine_spec", "slots": {"spec_mention": "八零果"}}],
    )
    parser, capture = build_eval_parser(
        FakeLlmClient(
            default={
                "acts": [
                    {
                        "type": "refine_spec",
                        "slots": {"spec_mention": "红富士80果一级烟台箱装"},
                    }
                ]
            }
        )
    )
    report = LanguageBenchmark().evaluate([case], parser, mode="fake", model="fake", capture=capture)
    row = report.records[0]
    assert report.veto is True
    assert row.l0_violated is True
    assert row.taxonomy == "guessed_sku"
    assert row.severity == "veto"
    assert row.model_pass is False


def test_guessed_customer_is_l0_veto():
    case = ParserEvaluationCase(
        id="open-wang-boss",
        text="开王老板的单",
        expected_acts=[{"type": "start_order", "slots": {"customer_mention": "王老板"}}],
    )
    parser, capture = build_eval_parser(
        FakeLlmClient(
            default={"acts": [{"type": "start_order", "slots": {"customer_mention": "王强水果店"}}]}
        )
    )
    report = LanguageBenchmark().evaluate([case], parser, mode="fake", model="fake", capture=capture)
    assert report.veto is True
    assert report.records[0].taxonomy == "guessed_customer"
    assert report.records[0].severity == "veto"


def test_sku_id_in_raw_is_veto_even_after_rule_fallback():
    case = ParserEvaluationCase(
        id="apple-60",
        text="苹果60件",
        expected_acts=[{"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}}],
    )
    parser, capture = build_eval_parser(
        FakeLlmClient(
            default={
                "acts": [
                    {
                        "type": "set_line",
                        "slots": {"product_mention": "苹果", "qty": 60, "sku_id": "fuji-80"},
                    }
                ]
            }
        )
    )
    report = LanguageBenchmark().evaluate([case], parser, mode="live", model="probe", capture=capture)
    row = report.records[0]
    assert row.fallback is True
    assert row.fallback_reason == "schema_validation_error"
    assert row.l0_violated is True
    assert row.severity == "veto"
    assert row.taxonomy == "l0_violation"
    assert report.scored is True
    assert row.model_pass is False


def test_unexpected_confirm_is_veto():
    case = ParserEvaluationCase(
        id="apple-60",
        text="苹果60件",
        expected_acts=[{"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}}],
    )
    parser, capture = build_eval_parser(
        FakeLlmClient(default={"acts": [{"type": "confirm_order", "slots": {}}]})
    )
    report = LanguageBenchmark().evaluate([case], parser, mode="fake", model="fake", capture=capture)
    assert report.records[0].taxonomy == "judged_confirm"
    assert report.records[0].severity == "veto"


def test_fallback_on_stall_oral_is_not_model_pass():
    case = ParserEvaluationCase(
        id="spec-80",
        tag="stall_oral",
        text="八零果",
        expected_acts=[{"type": "refine_spec", "slots": {"spec_mention": "八零果"}}],
    )
    parser, capture = build_eval_parser(FakeLlmClient(default="{not-json"))
    report = LanguageBenchmark().evaluate([case], parser, mode="live", model="probe", capture=capture)
    row = report.records[0]
    assert row.fallback is True
    assert row.fallback_reason
    assert row.taxonomy == "fallback_to_rule"
    assert row.severity == "fail"
    assert row.model_pass is False
    assert report.scored is True


def test_canonical_fallback_recovered_is_not_model_pass():
    case = ParserEvaluationCase(
        id="confirm",
        tag="canonical",
        text="好了",
        expected_acts=[{"type": "confirm_order", "slots": {}}],
    )
    parser, capture = build_eval_parser(FakeLlmClient(default="{not-json"))
    report = LanguageBenchmark().evaluate([case], parser, mode="fake", model="fake", capture=capture)
    row = report.records[0]
    assert row.taxonomy == "fallback_recovered"
    assert row.severity == "recovered"
    assert row.model_pass is False
    assert row.predicted_acts[0].type == "confirm_order"


def test_eval_uses_parser_v1_prompt_only():
    parser, capture = build_eval_parser(
        FakeLlmClient(default={"acts": [{"type": "confirm_order", "slots": {}}]})
    )
    parser.parse("好了")
    assert capture.last_system == PARSER_SYSTEM_PROMPT
    assert capture.last_user == "好了"
    assert "王强水果店" not in (capture.last_system or "")
    assert "红富士80" not in (capture.last_system or "")


def test_legacy_unscored_record_shape():
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
    assert report.records[0].severity == "pass"


def test_eval_module_does_not_touch_frozen_services():
    text = Path(__file__).resolve().parents[1].joinpath("agent/evaluation.py").read_text(encoding="utf-8")
    for needle in ("OrderService", "MemoryService", "DecisionPolicy", "ProductResolver", "confirm_gate"):
        assert needle not in text


def test_default_pytest_does_not_enable_live(monkeypatch):
    monkeypatch.delenv("RUN_LIVE_LLM", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert live_llm_enabled() is False


def test_client_error_records_detail_in_raw():
    case = ParserEvaluationCase(
        id="explicit-price",
        text="苹果按3块",
        expected_acts=[{"type": "set_price", "slots": {"product_mention": "苹果", "unit_price": 3}}],
    )
    parser, capture = build_eval_parser(
        FakeLlmClient(error=RuntimeError("client_error:http_429"))
    )
    report = LanguageBenchmark().evaluate(
        [case], parser, mode="live", model="qwen-probe", capture=capture
    )
    row = report.records[0]
    assert row.fallback is True
    assert row.fallback_reason == "client_error"
    assert row.raw == "client_error:http_429"
    assert row.model_pass is False
    assert row.taxonomy == "fallback_to_rule"


def test_live_pause_only_for_http_client(monkeypatch):
    from app.agent.evaluation import CaptureLlmClient, _live_http_pause
    from app.agent.llm_client import HttpLlmClient

    monkeypatch.setenv("LLM_EVAL_PAUSE", "0.4")
    http = CaptureLlmClient(HttpLlmClient(api_key="k", base_url="http://example/v1", model="m"))
    fake = CaptureLlmClient(FakeLlmClient(default={"acts": []}))
    assert _live_http_pause("live", http) == 0.4
    assert _live_http_pause("fake", http) == 0.0
    assert _live_http_pause("live", fake) == 0.0
    assert _live_http_pause("live", None) == 0.0


def test_add_item_on_open_order_counts_as_model_pass():
    case = ParserEvaluationCase(
        id="open-wang-apple",
        text="开老王的单苹果60件",
        expected_acts=[
            {"type": "start_order", "slots": {"customer_mention": "老王"}},
            {"type": "set_line", "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"}},
        ],
    )
    parser, capture = build_eval_parser(
        FakeLlmClient(
            default={
                "acts": [
                    {"type": "start_order", "slots": {"customer_mention": "老王"}},
                    {
                        "type": "add_item",
                        "slots": {"product_mention": "苹果", "qty": 60, "uom": "件"},
                    },
                ]
            }
        )
    )
    report = LanguageBenchmark().evaluate(
        [case], parser, mode="live", model="qwen-probe", capture=capture
    )
    row = report.records[0]
    assert row.fallback is False
    assert row.parser_name == "llm"
    assert row.model_pass is True
    assert row.severity == "pass"
    assert row.predicted_acts[1].type == "add_line"


def test_set_spec_on_oral_spec_counts_as_model_pass():
    case = ParserEvaluationCase(
        id="must-not-expand-sku-name",
        tag="must_not_guess",
        text="八零果",
        expected_acts=[{"type": "refine_spec", "slots": {"spec_mention": "八零果"}}],
    )
    parser, capture = build_eval_parser(
        FakeLlmClient(default={"acts": [{"type": "set_spec", "slots": {"spec_mention": "八零果"}}]})
    )
    report = LanguageBenchmark().evaluate(
        [case], parser, mode="live", model="qwen-probe", capture=capture
    )
    row = report.records[0]
    assert row.fallback is False
    assert row.model_pass is True
    assert row.l0_violated is False
    assert row.predicted_acts[0].type == "refine_spec"


def test_qwen_residual_slot_errors_count_as_model_pass():
    samples = [
        ParserEvaluationCase(
            id="add-golden-durian",
            text="加两个金边榴莲",
            expected_acts=[
                {"type": "add_line", "slots": {"product_mention": "金边榴莲", "qty": 2, "uom": "个"}}
            ],
        ),
        ParserEvaluationCase(
            id="add-more-qty",
            text="再加20件",
            expected_acts=[{"type": "set_qty", "slots": {"qty": 20, "uom": "件", "mode": "add"}}],
        ),
        ParserEvaluationCase(
            id="anaphora-that-apple",
            text="那个苹果",
            expected_acts=[{"type": "unknown", "slots": {"product_mention": "那个苹果"}}],
        ),
        ParserEvaluationCase(
            id="anaphora-just-now",
            text="刚才那个改80件",
            expected_acts=[
                {"type": "set_qty", "slots": {"product_mention": "刚才那个", "qty": 80, "uom": "件"}}
            ],
        ),
        ParserEvaluationCase(
            id="remove-that",
            tag="stall_oral",
            text="那个不要了",
            expected_acts=[{"type": "remove_line", "slots": {"product_mention": "那个"}}],
        ),
    ]
    raws = {
        "加两个金边榴莲": {
            "acts": [{"type": "add_line", "slots": {"product_mention": "金边榴莲", "qty": 2}}]
        },
        "再加20件": {"acts": [{"type": "add_line", "slots": {"qty": 20, "uom": "件"}}]},
        "那个苹果": {"acts": [{"type": "set_line", "slots": {"product_mention": "那个苹果"}}]},
        "刚才那个改80件": {
            "acts": [{"type": "set_qty", "slots": {"qty": 80, "uom": "件", "mention": "刚才那个"}}]
        },
        "那个不要了": {"acts": [{"type": "remove_line", "slots": {"mention": "那个"}}]},
    }
    parser, capture = build_eval_parser(FakeLlmClient(responses=raws))
    report = LanguageBenchmark().evaluate(
        samples, parser, mode="live", model="qwen-probe", capture=capture
    )
    assert report.veto is False
    assert report.stall_oral_pass_rate == 1.0
    for row in report.records:
        assert row.fallback is False
        assert row.model_pass is True, row.case_id
        assert row.severity == "pass"
