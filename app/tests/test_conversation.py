import json
from pathlib import Path

from app.bootstrap import build_world, new_session
from app.response.grounder import ReplyGrounder


def _cases() -> list[dict]:
    path = Path(__file__).resolve().parents[2] / "docs/dataset/sales_conversation_cases.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def test_conversation_dataset_covers_core_paths():
    ids = {c["id"] for c in _cases()}
    assert "burst-ack-no-price-question" in ids
    assert "homonym-must-not-leak-profile" in ids
    assert len(_cases()) >= 8


def test_conversation_cases_pass_on_template_generator():
    runner, _events, _catalog = build_world()
    grounder = ReplyGrounder()
    ask_tokens = ("哪一种", "多少钱", "要按老价格")
    for case in _cases():
        session = new_session()
        for turn in case["turns"]:
            result = runner.handle(session, turn["user"], expect_more=bool(turn.get("expect_more")))
            checks = turn.get("assert") or {}
            text = result.reply_text
            plan = result.reply_plan
            assert plan is not None, case["id"]
            assert grounder.check(text, plan).ok is True, f"{case['id']}: {text}"
            if "reply_mode" in checks:
                assert result.verdict.reply_mode == checks["reply_mode"], case["id"]
            if "reply_scope" in checks:
                assert plan.reply_scope == checks["reply_scope"], case["id"]
            if "confirm_ok" in checks:
                assert result.verdict.confirm_ok is checks["confirm_ok"], case["id"]
            if "question_code" in checks:
                assert plan.question is not None
                assert plan.question.code == checks["question_code"]
            if "line_count" in checks:
                assert len(session.draft.lines) == checks["line_count"], case["id"]
            for token in checks.get("must_include") or []:
                assert token in text, f"{case['id']} missing {token}: {text}"
            for token in checks.get("must_not_include") or []:
                assert token not in text, f"{case['id']} leaked {token}: {text}"
            if "price" in (checks.get("must_not_ask") or []):
                assert all(tok not in text for tok in ask_tokens)
                assert "多少钱" not in text
            if "sku" in (checks.get("must_not_ask") or []):
                assert "哪一种" not in text


def test_unbound_customer_does_not_leak_profile_or_price():
    runner, _events, _catalog = build_world()
    session = new_session()
    first = runner.handle(session, "开王老板的单")
    second = runner.handle(session, "苹果60件")
    for result in (first, second):
        text = result.reply_text
        assert "红富士" not in text
        assert "烟台" not in text
        assert "4.8" not in text
        assert "王强水果店" in text
        assert "王记水果店" in text
        assert result.verdict.reply_mode == "ask"
        assert result.reply_plan is not None
        assert all(ref.kind != "price" for ref in result.reply_plan.source_refs)
        assert all(ref.kind != "sku" or ref.origin == "issue_option" for ref in result.reply_plan.source_refs)
