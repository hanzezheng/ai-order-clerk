from __future__ import annotations

from app.entity.catalog import CustomerProfile, CustomerRef, ProductMention
from app.entity.context import BusinessContext
from app.entity.issue import DecisionVerdict, Issue
from app.entity.session import SalesSession
from app.services.catalog_service import OntologyService


class DecisionPolicy:
    def __init__(self, ontology: OntologyService) -> None:
        self._ontology = ontology

    def on_start_order(self, ref: CustomerRef) -> DecisionVerdict:
        if ref.id and not ref.candidates:
            return DecisionVerdict(allow_execute=True, reasons=["customer_unique"])
        if ref.candidates:
            return DecisionVerdict(
                allow_execute=False,
                issues=[
                    Issue(
                        code="customer_ambiguous",
                        block_level="session_block",
                        ask_when="now",
                        options=[
                            {
                                "id": str(c.id),
                                "name": c.name,
                                "stall_no": c.stall_no,
                                "phone_tail": c.phone_tail,
                            }
                            for c in ref.candidates
                        ],
                        message="有多个王老板，请问是哪一家？",
                    )
                ],
                reply_mode="ask",
                reasons=["customer_ambiguous"],
            )
        return DecisionVerdict(
            allow_execute=False,
            issues=[
                Issue(
                    code="customer_not_found",
                    block_level="session_block",
                    message="没找到这位老板",
                    ask_when="now",
                )
            ],
            reply_mode="ask",
            reasons=["customer_not_found"],
        )

    def fill_sku(self, mention: ProductMention, profile: CustomerProfile | None) -> ProductMention:
        node = mention.matched_node
        if node is None:
            return mention
        if node.level == "sku":
            mention.resolved_sku = node
            mention.resolve_level = "sku"
            mention.filled_from = "explicit"
            return mention
        if profile:
            sku_id = profile.product_defaults.get(str(node.id))
            if sku_id:
                sku = self._ontology.get(sku_id)
                if sku:
                    mention.resolved_sku = sku
                    mention.resolve_level = "sku"
                    mention.filled_from = "profile"
                    return mention
        unique = self._ontology.unique_active_sku(node)
        if unique:
            mention.resolved_sku = unique
            mention.resolve_level = "sku"
            mention.filled_from = "ontology_unique_child"
            return mention
        return mention

    def on_line(self, mention: ProductMention, *, expect_more: bool) -> DecisionVerdict:
        issues: list[Issue] = []
        reasons: list[str] = []
        if mention.matched_node is None:
            return DecisionVerdict(
                allow_execute=False,
                issues=[Issue(code="product_unknown", block_level="line_hold", message="没听清是哪个货")],
                reasons=["product_unknown"],
            )
        if mention.resolved_sku is None:
            issues.append(
                Issue(
                    code="product_ambiguous",
                    block_level="line_hold",
                    ask_when="idle" if expect_more else "now",
                    options=[{"id": str(c.id), "name": c.name} for c in mention.candidates],
                    message="先记下这个品，规格还没定",
                )
            )
            reasons.append("product_ambiguous")
        else:
            if mention.filled_from == "profile":
                reasons.append("profile_default_sku")
            elif mention.filled_from == "ontology_unique_child":
                reasons.append("ontology_unique_child")
        issues.append(
            Issue(
                code="price_tbd",
                block_level="notice",
                ask_when="idle",
                message="价未定",
            )
        )
        reasons.append("price_tbd")
        return DecisionVerdict(allow_execute=True, issues=issues, reasons=reasons, reply_mode="ack" if expect_more else "recap")

    def on_set_price(self, mention: ProductMention) -> DecisionVerdict:
        if mention.matched_node is None:
            return DecisionVerdict(
                allow_execute=False,
                issues=[Issue(code="product_unknown", block_level="line_hold", message="没听清给哪个货定价")],
                reasons=["product_unknown"],
            )
        return DecisionVerdict(allow_execute=True, reasons=["price_explicit"], reply_mode="ack")

    def confirm_gate(self, session: SalesSession) -> DecisionVerdict:
        issues: list[Issue] = []
        if session.pending_customer_candidates:
            issues.append(
                Issue(code="customer_ambiguous", block_level="session_block", message="客户未确定，不能确认")
            )
        if session.draft.customer is None or session.draft.customer.id is None:
            issues.append(Issue(code="customer_missing", block_level="session_block", message="还没开谁的单"))
        if not session.draft.lines:
            issues.append(Issue(code="empty_order", block_level="session_block", message="还没有货"))
        for line in session.draft.lines:
            if not line.product_sku_id:
                issues.append(
                    Issue(
                        code="line_unresolved",
                        block_level="line_hold",
                        subject_line_id=line.line_id,
                        message="有行还没落到可履约规格",
                    )
                )
        blocking = [i for i in issues if i.block_level in {"session_block", "line_hold"}]
        return DecisionVerdict(
            allow_execute=not blocking,
            confirm_ok=not blocking,
            issues=issues,
            reasons=["confirm_ok"] if not blocking else [i.code for i in blocking],
            reply_mode="recap" if not blocking else "ask",
        )

    def collect_notices(self, session: SalesSession, context: BusinessContext) -> list[Issue]:
        """由 BusinessContext 产出 notice。不改订单、不写 Memory。"""
        if context.customer_id is None:
            return []
        if session.draft.customer is None or session.draft.customer.id is None:
            return []
        lines = {ln.line_id: ln for ln in session.draft.lines}
        issues: list[Issue] = []
        for item in context.profile_defaults:
            issues.append(
                Issue(
                    code="profile_default_used",
                    block_level="notice",
                    ask_when="idle",
                    subject_line_id=item.line_id,
                    options=[{"sku_name": item.sku_name}],
                )
            )
        for fact in context.price_facts:
            line = lines.get(fact.line_id) if fact.line_id else None
            if line is not None and line.price.source == "explicit":
                continue
            amount = str(int(fact.unit_price)) if fact.unit_price == fact.unit_price.to_integral_value() else str(fact.unit_price)
            payload = {
                "unit_price": amount,
                "price_uom": fact.price_uom,
                "price_type": fact.price_type,
            }
            if fact.expired:
                issues.append(
                    Issue(
                        code="price_memory_expired",
                        block_level="notice",
                        ask_when="idle",
                        subject_line_id=fact.line_id,
                        options=[payload],
                    )
                )
                continue
            if fact.price_type == "last_deal":
                issues.append(
                    Issue(
                        code="last_deal_available_not_applied",
                        block_level="notice",
                        ask_when="idle",
                        subject_line_id=fact.line_id,
                        options=[payload],
                    )
                )
            elif fact.price_type == "market_today":
                issues.append(
                    Issue(
                        code="market_hint_not_applied",
                        block_level="notice",
                        ask_when="idle",
                        subject_line_id=fact.line_id,
                        options=[payload],
                    )
                )
        return issues
