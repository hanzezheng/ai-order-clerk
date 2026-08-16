from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.entity.issue import DecisionVerdict
from app.entity.order import OrderLine
from app.entity.reply import ReplyLineFact, ReplyPlan, ReplyQuestion, SourceRef
from app.entity.session import SalesSession


def _num(value: Decimal) -> str:
    if value == value.to_integral_value():
        return str(int(value))
    return format(value, "f").rstrip("0").rstrip(".")


def _refs_for_line(fact: ReplyLineFact) -> list[SourceRef]:
    refs = [
        SourceRef(kind="sku", text=fact.label, origin="draft_line", subject_id=fact.line_id),
        SourceRef(kind="qty", text=fact.qty_text, origin="draft_line", subject_id=fact.line_id),
    ]
    if fact.uom:
        refs.append(SourceRef(kind="uom", text=fact.uom, origin="draft_line", subject_id=fact.line_id))
    if fact.sku_text:
        refs.append(SourceRef(kind="sku", text=fact.sku_text, origin="draft_line", subject_id=fact.line_id))
    if fact.price_text:
        refs.append(SourceRef(kind="price", text=fact.price_text, origin="draft_line", subject_id=fact.line_id))
    if fact.price_uom:
        refs.append(SourceRef(kind="uom", text=fact.price_uom, origin="draft_line", subject_id=fact.line_id))
    return refs


def _line_fact(line: OrderLine) -> ReplyLineFact:
    matched = line.mention.matched_node.name if line.mention.matched_node else line.mention.raw
    sku = line.mention.resolved_sku.name if line.mention.resolved_sku else None
    price_text = None
    price_uom = None
    if line.price.source == "explicit" and line.price.unit_price is not None:
        price_text = _num(line.price.unit_price)
        price_uom = line.price.price_uom or "块"
    return ReplyLineFact(
        line_id=line.line_id,
        label=matched or line.mention.raw,
        qty_text=_num(line.qty.value),
        uom=line.qty.uom,
        price_text=price_text,
        price_uom=price_uom,
        price_tbd=line.price.source == "tbd",
        from_profile=line.mention.filled_from == "profile",
        sku_text=sku,
    )


def build_reply_plan(
    session: SalesSession,
    verdict: DecisionVerdict,
    *,
    changed_line_ids: list[UUID] | None = None,
) -> ReplyPlan:
    """只读快照 + 已聚合 verdict。不改裁决，不读 Catalog。"""
    changed = list(changed_line_ids or [])
    confirmed = session.draft.status == "confirmed"
    scope = "changed_only" if verdict.reply_mode == "ack" and not confirmed else "full"

    pending = list(session.pending_customer_candidates)
    amb = next((i for i in verdict.issues if i.code == "customer_ambiguous"), None)
    if pending or (amb and session.draft.customer is None):
        labels = [c.name for c in pending if c.name]
        if not labels and amb:
            labels = [str(opt.get("name") or "") for opt in amb.options if opt.get("name")]
        refs = [SourceRef(kind="customer", text=name, origin="issue_option") for name in labels]
        return ReplyPlan(
            mode=verdict.reply_mode,
            reply_scope="full",
            confirmed=False,
            question=ReplyQuestion(code="customer_ambiguous", option_labels=labels),
            source_refs=refs,
        )

    customer_label = session.draft.customer.name if session.draft.customer else None
    refs: list[SourceRef] = []
    if customer_label:
        refs.append(SourceRef(kind="customer", text=customer_label, origin="customer_ref"))

    source_lines = session.draft.lines
    if scope == "changed_only" and changed:
        idset = set(changed)
        source_lines = [ln for ln in session.draft.lines if ln.line_id in idset]

    facts = [_line_fact(ln) for ln in source_lines]
    for fact in facts:
        refs.extend(_refs_for_line(fact))

    must_say: list[str] = []
    if any(f.price_tbd for f in facts) and scope == "full":
        must_say.append("price_tbd")
    if any(f.from_profile for f in facts) and scope == "full":
        must_say.append("profile_default")

    return ReplyPlan(
        mode=verdict.reply_mode,
        reply_scope=scope,
        confirmed=confirmed,
        customer_label=customer_label,
        lines=facts,
        source_refs=refs,
        must_say=must_say,
    )
