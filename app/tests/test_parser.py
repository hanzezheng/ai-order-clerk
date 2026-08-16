from app.agent.turn_parser import RuleTurnParser
from app.database.memory import InMemoryCatalog
from app.services.catalog_service import OntologyService


def test_parse_burst_and_durian_correction():
    ontology = OntologyService(InMemoryCatalog())
    parsed = RuleTurnParser().parse(
        "苹果60件梨60件加两个金边榴莲不对榴莲改三个",
        ontology.alias_table(),
    )
    types = [a.type for a in parsed.acts]
    assert types == ["set_line", "set_line", "add_line", "set_qty"]
    assert parsed.acts[0].slots["product_mention"] == "苹果"
    assert parsed.acts[0].slots["qty"] == 60
    assert parsed.acts[2].slots["product_mention"] == "金边榴莲"
    assert parsed.acts[2].slots["qty"] == 2
    assert parsed.acts[3].slots["product_mention"] == "榴莲"
    assert parsed.acts[3].slots["qty"] == 3
