from __future__ import annotations

from uuid import UUID

from app.entity.catalog import ProductQuery

_SPEC_TOKENS: tuple[tuple[str, dict[str, str]], ...] = (
    ("八十果", {"size": "80"}),
    ("八零果", {"size": "80"}),
    ("80果", {"size": "80"}),
    ("80#", {"size": "80"}),
    ("九十果", {"size": "90"}),
    ("90果", {"size": "90"}),
    ("90#", {"size": "90"}),
    ("烟台的", {"origin": "烟台"}),
    ("烟台", {"origin": "烟台"}),
    ("一级", {"grade": "一级"}),
    ("统货", {"grade": "统货"}),
    ("箱装", {"packing": "箱装"}),
)

_SPEC_KEYS = ("size", "grade", "origin", "packing")


def normalize_spec(text: str | None) -> dict[str, str]:
    """口语规格 → 属性。不映射 SKU。"""
    if not text:
        return {}
    found: dict[str, str] = {}
    rest = text
    for token, attrs in sorted(_SPEC_TOKENS, key=lambda item: len(item[0]), reverse=True):
        if token in rest:
            found.update(attrs)
            rest = rest.replace(token, "")
    return {key: found[key] for key in _SPEC_KEYS if key in found}


class ProductUnderstanding:
    """SpeechAct 语言槽 → ProductQuery。禁止写 Catalog / Memory，禁止选 SKU。"""

    def interpret(
        self,
        *,
        product_mention: str = "",
        spec_mention: str | None = None,
        focus_node_id: UUID | None = None,
    ) -> ProductQuery:
        product = (product_mention or "").strip()
        spec = (spec_mention or "").strip() or None
        attributes = normalize_spec(spec)
        lookup = product
        for token, attrs in sorted(_SPEC_TOKENS, key=lambda item: len(item[0]), reverse=True):
            if token in lookup:
                attributes.update(attrs)
                lookup = lookup.replace(token, "")
        lookup = lookup.strip()
        attributes = {key: attributes[key] for key in _SPEC_KEYS if key in attributes}
        raw = product or spec or ""
        return ProductQuery(
            raw=raw,
            lookup_text=lookup,
            product_mention=product,
            spec_mention=spec,
            attributes=attributes,
            focus_node_id=focus_node_id,
        )
