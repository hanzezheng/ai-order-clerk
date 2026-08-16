from __future__ import annotations

from dataclasses import dataclass

from app.database.memory import InMemoryAliasStore, InMemoryPriceStore
from app.entity.memory import MemoryCandidate
from app.memory.policy import MemoryDecision


@dataclass(frozen=True)
class MemoryService:
    aliases: InMemoryAliasStore
    prices: InMemoryPriceStore

    def apply(self, candidate: MemoryCandidate, decision: MemoryDecision) -> None:
        if not decision.write:
            return
        if candidate.alias is not None:
            self.aliases.put(candidate.alias.alias, candidate.alias.node_id)
        if candidate.price is not None:
            self.prices.put(candidate.price)
