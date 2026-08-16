from __future__ import annotations

from app.entity.context import BusinessContext, PriceRiskFact, ProfileDefaultFact
from app.entity.session import SalesSession
from app.services.ports import CatalogRepository, PriceMemoryRepository
from app.services.price_memory_service import PriceMemoryService

_PRICE_TYPES = ("last_deal", "last_quote", "market_today")


class ContextLoader:
    """绑客户后投影本单相关事实。未绑定则空，且不访问 Profile/PriceMemory。"""

    def __init__(self, catalog: CatalogRepository, prices: PriceMemoryRepository) -> None:
        self._catalog = catalog
        self._prices = PriceMemoryService(prices)

    def load(self, session: SalesSession) -> BusinessContext:
        customer = session.draft.customer
        if customer is None or customer.id is None:
            return BusinessContext()
        profile = self._catalog.get_profile(customer.id)
        defaults: list[ProfileDefaultFact] = []
        facts: list[PriceRiskFact] = []
        for line in session.draft.lines:
            if line.mention.filled_from == "profile" and line.mention.resolved_sku:
                sku = line.mention.resolved_sku
                defaults.append(
                    ProfileDefaultFact(line_id=line.line_id, sku_id=sku.id, sku_name=sku.name)
                )
            sku_id = line.product_sku_id
            if sku_id is None:
                continue
            for price_type in _PRICE_TYPES:
                lookup = self._prices.lookup(
                    customer_id=customer.id,
                    product_id=sku_id,
                    price_type=price_type,
                )
                rec = lookup.record
                if rec is None:
                    continue
                facts.append(
                    PriceRiskFact(
                        line_id=line.line_id,
                        sku_id=sku_id,
                        price_type=rec.price_type,
                        unit_price=rec.unit_price,
                        price_uom=rec.price_uom,
                        expired=lookup.expired,
                    )
                )
        return BusinessContext(
            customer_id=customer.id,
            profile_defaults=defaults,
            price_facts=facts,
        )
