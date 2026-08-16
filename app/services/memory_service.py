from __future__ import annotations

from dataclasses import dataclass

from app.database.memory import InMemoryAliasStore, InMemoryCatalog, InMemoryPriceStore
from app.entity.memory import MemoryCandidate
from app.memory.policy import MemoryDecision


@dataclass(frozen=True)
class MemoryService:
    aliases: InMemoryAliasStore
    prices: InMemoryPriceStore
    catalog: InMemoryCatalog | None = None

    def apply(self, candidate: MemoryCandidate, decision: MemoryDecision) -> None:
        if not decision.write:
            return
        if candidate.kind == "product_default" and self.catalog is not None:
            if candidate.customer_id is None or candidate.node_id is None or candidate.sku_id is None:
                return
            self.catalog.put_product_default(candidate.customer_id, candidate.node_id, candidate.sku_id)
            return
        if candidate.alias is not None:
            self.aliases.put(candidate.alias.alias, candidate.alias.node_id)
        if candidate.price is not None:
            self.prices.put(candidate.price)
