from inspect import signature

from app.entity.reply import ReplyLineFact, ReplyPlan, ReplyQuestion, SourceRef
from app.response.grounder import ReplyGrounder
from app.response.template import TemplateResponseGenerator
from app.session.runner import SalesSessionRunner


def _plan_apple() -> ReplyPlan:
    return ReplyPlan(
        mode="recap",
        reply_scope="full",
        confirmed=False,
        customer_label="李记果行",
        lines=[
            ReplyLineFact(
                label="苹果",
                qty_text="60",
                uom="件",
                price_tbd=True,
                from_profile=True,
                sku_text="红富士80果一级烟台箱装",
            )
        ],
        source_refs=[
            SourceRef(kind="customer", text="李记果行", origin="customer_ref"),
            SourceRef(kind="qty", text="60", origin="draft_line"),
            SourceRef(kind="uom", text="件", origin="draft_line"),
            SourceRef(kind="sku", text="苹果", origin="draft_line"),
            SourceRef(kind="sku", text="红富士80果一级烟台箱装", origin="draft_line"),
        ],
        must_say=["price_tbd", "profile_default"],
    )


def test_runner_has_no_private_reply():
    assert hasattr(SalesSessionRunner, "_reply") is False


def test_generator_signature_only_takes_plan():
    params = list(signature(TemplateResponseGenerator.generate).parameters)
    assert params == ["self", "plan"]


def test_template_recap_includes_profile_sku_and_tbd():
    text = TemplateResponseGenerator().generate(_plan_apple())
    assert "红富士80果一级烟台箱装" in text
    assert "60" in text
    assert "价未定" in text
    assert ReplyGrounder().check(text, _plan_apple()).ok is True


def test_ack_changed_only_does_not_require_full_order():
    plan = ReplyPlan(
        mode="ack",
        reply_scope="changed_only",
        lines=[ReplyLineFact(label="梨", qty_text="60", uom="件", price_tbd=True)],
        source_refs=[
            SourceRef(kind="sku", text="梨", origin="draft_line"),
            SourceRef(kind="qty", text="60", origin="draft_line"),
            SourceRef(kind="uom", text="件", origin="draft_line"),
        ],
    )
    text = TemplateResponseGenerator().generate(plan)
    assert text.startswith("记下了")
    assert "梨" in text
    assert "红富士" not in text
    assert "哪一种" not in text
    assert "多少钱" not in text
    assert ReplyGrounder().check(text, plan).ok is True


def test_grounder_rejects_number_not_in_source_refs():
    plan = _plan_apple()
    forged = TemplateResponseGenerator().generate(plan) + "4.8"
    result = ReplyGrounder().check(forged, plan)
    assert result.ok is False
    assert result.leftover


def test_ask_customer_only_uses_option_names():
    plan = ReplyPlan(
        mode="ask",
        reply_scope="full",
        question=ReplyQuestion(code="customer_ambiguous", option_labels=["王强水果店", "王记水果店"]),
        source_refs=[
            SourceRef(kind="customer", text="王强水果店", origin="issue_option"),
            SourceRef(kind="customer", text="王记水果店", origin="issue_option"),
        ],
    )
    text = TemplateResponseGenerator().generate(plan)
    assert "王强水果店" in text
    assert "王记水果店" in text
    assert "红富士" not in text
    assert ReplyGrounder().check(text, plan).ok is True
