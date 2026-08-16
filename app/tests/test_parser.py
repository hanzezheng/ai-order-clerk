from inspect import signature

from app.agent.turn_parser import RuleTurnParser


def test_parse_signature_has_no_alias_table():
    params = list(signature(RuleTurnParser.parse).parameters)
    assert params == ["self", "text"]


def test_parse_burst_and_durian_correction_without_catalog():
    parsed = RuleTurnParser().parse("苹果60件梨60件加两个金边榴莲不对榴莲改三个")
    types = [a.type for a in parsed.acts]
    assert types == ["set_line", "set_line", "add_line", "set_qty"]
    assert parsed.acts[0].slots["product_mention"] == "苹果"
    assert parsed.acts[0].slots["qty"] == 60
    assert parsed.acts[2].slots["product_mention"] == "金边榴莲"
    assert parsed.acts[2].slots["qty"] == 2
    assert parsed.acts[3].slots["product_mention"] == "榴莲"
    assert parsed.acts[3].slots["qty"] == 3
    assert "node" not in parsed.acts[0].slots
    assert "product_id" not in parsed.acts[0].slots


def test_parse_set_price_is_linguistic_only():
    parsed = RuleTurnParser().parse("苹果按3块")
    assert len(parsed.acts) == 1
    assert parsed.acts[0].type == "set_price"
    assert parsed.acts[0].slots["product_mention"] == "苹果"
    assert parsed.acts[0].slots["unit_price"] == 3
