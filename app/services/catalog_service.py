from __future__ import annotations

from uuid import UUID

from app.entity.catalog import CustomerProfile, CustomerRecord, CustomerRef, ProductMention, ProductNode
from app.services.ports import CatalogRepository


class OntologyService:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    def alias_table(self) -> list[tuple[str, UUID]]:
        pairs: list[tuple[str, UUID]] = []
        for node in self._catalog.list_nodes():
            names = [node.name, *node.aliases]
            for name in names:
                if name:
                    pairs.append((name, node.id))
        pairs.sort(key=lambda item: len(item[0]), reverse=True)
        return pairs

    def get(self, node_id: UUID) -> ProductNode | None:
        return self._catalog.get_node(node_id)

    def lookup(self, raw: str) -> ProductMention:
        text = raw.strip()
        for alias, node_id in self.alias_table():
            if text == alias or text.startswith(alias):
                node = self._catalog.get_node(node_id)
                if node is None:
                    continue
                return ProductMention(
                    raw=text,
                    matched_node=node,
                    resolve_level=node.level,
                    confidence=0.95 if text == alias else 0.85,
                    candidates=self._sku_candidates(node),
                )
        return ProductMention(raw=text, confidence=0.0)

    def children(self, node_id: UUID) -> list[ProductNode]:
        return [n for n in self._catalog.list_nodes() if n.parent_id == node_id]

    def ancestors(self, node: ProductNode) -> list[ProductNode]:
        out: list[ProductNode] = []
        current = node
        while current.parent_id:
            parent = self._catalog.get_node(current.parent_id)
            if parent is None:
                break
            out.append(parent)
            current = parent
        return out

    def descendant_skus(self, node: ProductNode) -> list[ProductNode]:
        if node.level == "sku":
            return [node] if node.status == "active" else []
        found: list[ProductNode] = []
        stack = [node]
        while stack:
            cur = stack.pop()
            for child in self.children(cur.id):
                if child.status != "active":
                    continue
                if child.level == "sku":
                    found.append(child)
                else:
                    stack.append(child)
        return found

    def unique_active_sku(self, node: ProductNode) -> ProductNode | None:
        skus = self.descendant_skus(node)
        if len(skus) == 1:
            return skus[0]
        return None

    def related(self, a: ProductNode, b: ProductNode) -> bool:
        """同一条本体路径上（祖先/后代），不是仅共享品类。"""
        if a.id == b.id:
            return True
        a_up = {a.id, *[x.id for x in self.ancestors(a)]}
        b_up = {b.id, *[x.id for x in self.ancestors(b)]}
        return a.id in b_up or b.id in a_up

    def same_variety(self, a: ProductNode, b: ProductNode) -> bool:
        """同一品种下的规格改口可合行；跨品种（苹果/梨）不合。"""
        left = self._variety_id(a)
        right = self._variety_id(b)
        return left is not None and left == right

    def _variety_id(self, node: ProductNode) -> UUID | None:
        if node.level == "variety":
            return node.id
        for ancestor in self.ancestors(node):
            if ancestor.level == "variety":
                return ancestor.id
        return None

    def _sku_candidates(self, node: ProductNode) -> list[ProductNode]:
        return self.descendant_skus(node)


class CustomerService:
    def __init__(self, catalog: CatalogRepository) -> None:
        self._catalog = catalog

    def lookup(self, mention: str) -> CustomerRef:
        mention = mention.strip().rstrip("的")
        hits: list[CustomerRecord] = []
        for customer in self._catalog.list_customers():
            keys = [customer.display_name, customer.legal_name, *customer.aliases]
            if mention in keys:
                hits.append(customer)
        if not hits:
            for customer in self._catalog.list_customers():
                if mention and mention in customer.legal_name:
                    hits.append(customer)
        refs = [self._to_ref(c, 0.95) for c in hits]
        if len(refs) == 1:
            return refs[0]
        if len(refs) > 1:
            return CustomerRef(
                name=mention,
                match_confidence=0.5,
                candidates=refs,
            )
        return CustomerRef(name=mention, match_confidence=0.0, candidates=[])

    def match_candidate(self, mention: str, candidates: list[CustomerRef]) -> CustomerRef | None:
        text = mention.strip()
        for ref in candidates:
            if text in {ref.name, *(ref.aliases or [])}:
                return ref
            if ref.stall_no and (text == ref.stall_no or text == f"{ref.stall_no}号档" or f"{ref.stall_no}号" in text):
                return ref
            if ref.name and (text == ref.name or text in ref.name or ref.name in text):
                return ref
            if any(text == a or a in text for a in (ref.aliases or [])):
                if text not in {"王老板", "老王"}:
                    return ref
            if ref.phone_tail and text.endswith(ref.phone_tail):
                return ref
        return None

    def get_profile(self, customer_id: UUID) -> CustomerProfile | None:
        return self._catalog.get_profile(customer_id)

    def _to_ref(self, customer: CustomerRecord, confidence: float) -> CustomerRef:
        phone = customer.phones[0] if customer.phones else None
        return CustomerRef(
            id=customer.id,
            name=customer.legal_name,
            stall_no=customer.stall_no,
            phone_tail=phone[-4:] if phone else None,
            aliases=[customer.display_name, *customer.aliases],
            match_confidence=confidence,
        )
