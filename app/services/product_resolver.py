from __future__ import annotations

from app.database.memory import InMemoryAliasStore
from app.entity.catalog import ProductMention, ProductNode
from app.services.catalog_service import OntologyService
from app.services.ports import CatalogRepository


class ProductResolver:
    """product_mention → ProductMention。只识别，不写 Memory，不套档案默认。"""

    def __init__(self, catalog: CatalogRepository, aliases: InMemoryAliasStore) -> None:
        self._catalog = catalog
        self._aliases = aliases
        self._ontology = OntologyService(catalog)

    def resolve(self, raw: str) -> ProductMention:
        text = (raw or "").strip()
        if not text:
            return ProductMention(raw=raw or "", confidence=0.0)

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

    def _to_mention(self, text: str, node: ProductNode, *, confidence: float) -> ProductMention:
        return ProductMention(
            raw=text,
            matched_node=node,
            resolve_level=node.level,
            confidence=confidence,
            candidates=self._ontology.descendant_skus(node),
        )
