from __future__ import annotations

from app.entity.catalog import ProductMention, ProductNode, ProductQuery, ResolutionCandidate
from app.services.catalog_service import OntologyService
from app.services.ports import AliasRepository, CatalogRepository


class ProductResolver:
    """ProductQuery / 原文 → ProductMention。只识别与过滤候选，不写 Memory，不替品。"""

    def __init__(self, catalog: CatalogRepository, aliases: AliasRepository) -> None:
        self._catalog = catalog
        self._aliases = aliases
        self._ontology = OntologyService(catalog)

    def resolve(self, raw: str) -> ProductMention:
        return self.resolve_query(ProductQuery(raw=raw or "", lookup_text=(raw or "").strip(), product_mention=raw or ""))

    def resolve_query(self, query: ProductQuery) -> ProductMention:
        mention = self._identify(query)
        return self._constrain(mention, query)

    def _identify(self, query: ProductQuery) -> ProductMention:
        lookup = (query.lookup_text or "").strip()
        if lookup:
            found = self._match_text(lookup)
            if found.matched_node is not None:
                found.raw = query.raw or lookup
                return found
        if query.focus_node_id is not None:
            node = self._catalog.get_node(query.focus_node_id)
            if node is not None:
                skus = self._ontology.descendant_skus(node) or ([node] if node.level == "sku" else [])
                return ProductMention(
                    raw=query.raw or query.spec_mention or lookup,
                    matched_node=node,
                    resolve_level=node.level,
                    confidence=0.9,
                    candidates=list(skus),
                )
        original = (query.product_mention or query.spec_mention or query.raw or "").strip()
        if original and original != lookup:
            found = self._match_text(original)
            found.raw = query.raw or original
            return found
        return ProductMention(raw=query.raw or original, confidence=0.0)

    def _match_text(self, text: str) -> ProductMention:
        if not text:
            return ProductMention(raw=text, confidence=0.0)
        remembered = self._aliases.get(text)
        if remembered is not None:
            node = self._catalog.get_node(remembered)
            if node is not None:
                return self._to_mention(text, node, confidence=0.96)
        best: ProductNode | None = None
        best_len = -1
        for alias, node_id in self._ontology.alias_table():
            node = self._catalog.get_node(node_id)
            if node is None:
                continue
            if text == alias:
                return self._to_mention(text, node, confidence=0.95)
            if text.startswith(alias) and len(alias) > best_len:
                best = node
                best_len = len(alias)
        if best is not None:
            return self._to_mention(text, best, confidence=0.85)
        return ProductMention(raw=text, confidence=0.0)

    def _constrain(self, mention: ProductMention, query: ProductQuery) -> ProductMention:
        if not query.attributes:
            return mention
        pool = list(mention.candidates)
        if mention.matched_node is not None:
            if mention.matched_node.level == "sku":
                pool = [mention.matched_node]
            elif not pool:
                pool = self._ontology.descendant_skus(mention.matched_node)
        filtered: list[ResolutionCandidate] = []
        for sku in pool:
            if sku.level != "sku" or sku.status != "active":
                continue
            matched_on = _attribute_hits(sku, query.attributes)
            if matched_on is None:
                continue
            filtered.append(ResolutionCandidate(node=sku, matched_on=matched_on, gaps=[]))
        mention.resolution_candidates = filtered
        mention.candidates = [item.node for item in filtered]
        if len(filtered) == 1:
            sku = filtered[0].node
            mention.matched_node = sku
            mention.resolve_level = "sku"
            mention.confidence = max(mention.confidence, 0.93)
        elif len(filtered) == 0 and mention.matched_node is not None and mention.matched_node.level == "sku":
            parent = self._catalog.get_node(mention.matched_node.parent_id) if mention.matched_node.parent_id else None
            mention.matched_node = parent
            mention.resolve_level = parent.level if parent is not None else None
            mention.resolved_sku = None
        return mention

    def _to_mention(self, text: str, node: ProductNode, *, confidence: float) -> ProductMention:
        return ProductMention(
            raw=text,
            matched_node=node,
            resolve_level=node.level,
            confidence=confidence,
            candidates=self._ontology.descendant_skus(node),
        )


def _attribute_hits(node: ProductNode, required: dict[str, str]) -> list[str] | None:
    hits: list[str] = []
    attrs = node.attributes or {}
    for key, value in required.items():
        actual = attrs.get(key)
        if actual is None or str(actual) != str(value):
            return None
        hits.append(f"attr:{key}")
    return hits
