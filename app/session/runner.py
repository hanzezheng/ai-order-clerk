from __future__ import annotations

from decimal import Decimal

from app.entity.catalog import CustomerProfile, ProductMention
from app.entity.issue import DecisionVerdict, Issue
from app.entity.order import Quantity
from app.entity.session import SalesSession, TurnResult
from app.entity.speech import SpeechAct
from app.agent.turn_parser import RuleTurnParser
from app.policy.decision import DecisionPolicy
from app.services.catalog_service import CustomerService, OntologyService
from app.services.order_service import OrderService
from app.services.ports import SessionRepository


class SalesSessionRunner:
    """parse → policy → service。不访问 ORM。"""

    def __init__(
        self,
        *,
        parser: RuleTurnParser,
        policy: DecisionPolicy,
        customers: CustomerService,
        ontology: OntologyService,
        orders: OrderService,
        sessions: SessionRepository,
    ) -> None:
        self._parser = parser
        self._policy = policy
        self._customers = customers
        self._ontology = ontology
        self._orders = orders
        self._sessions = sessions

    def handle(self, session: SalesSession, text: str, *, expect_more: bool = False) -> TurnResult:
        session.turn_index += 1
        parsed = self._parser.parse(text, self._ontology.alias_table())
        acts = list(parsed.acts)
        if session.pending_customer_candidates and not (acts and acts[0].type == "start_order"):
            extras = [a for a in acts if a.type not in {"unknown", "clarify"}]
            acts = [SpeechAct(type="clarify", slots={"mention": text})] + extras

        all_issues: list[Issue] = []
        reasons: list[str] = []
        executed: list[str] = []
        last_verdict = DecisionVerdict()

        for act in acts:
            last_verdict = self._apply(session, act, expect_more=expect_more)
            all_issues.extend(last_verdict.issues)
            reasons.extend(last_verdict.reasons)
            if last_verdict.allow_execute:
                executed.append(act.type)

        confirm_ok = False
        if any(a.type == "confirm_order" for a in acts):
            gate = self._policy.confirm_gate(session)
            all_issues.extend(gate.issues)
            confirm_ok = gate.confirm_ok
            if gate.confirm_ok:
                self._orders.confirm(session)
                executed.append("confirm_order")
            reasons.extend(gate.reasons)

        reply_mode = "ack" if expect_more else ("ask" if any(i.block_level == "session_block" for i in all_issues) else "recap")
        if any(i.block_level == "session_block" and i.ask_when == "now" for i in all_issues) and not expect_more:
            reply_mode = "ask"

        verdict = DecisionVerdict(
            allow_execute=True,
            issues=all_issues,
            confirm_ok=confirm_ok,
            reasons=reasons,
            reply_mode=reply_mode,
        )
        session.deferred_issues = [i for i in all_issues if i.ask_when == "idle"]
        self._sessions.save(session)
        return TurnResult(
            reply_text=self._reply(session, verdict, expect_more=expect_more),
            session=session,
            verdict=verdict,
            acts=acts,
            commands_executed=executed,
        )

    def _apply(self, session: SalesSession, act: SpeechAct, *, expect_more: bool) -> DecisionVerdict:
        if act.type == "start_order":
            ref = self._customers.lookup(str(act.slots.get("customer_mention", "")))
            verdict = self._policy.on_start_order(ref)
            if not verdict.allow_execute:
                session.pending_customer_candidates = ref.candidates
                return verdict
            assert ref.id is not None
            self._orders.start_draft(session, ref)
            return verdict

        if act.type == "clarify":
            mention = str(act.slots.get("mention") or act.span or "")
            chosen = self._customers.match_candidate(mention, session.pending_customer_candidates)
            if chosen is None:
                return DecisionVerdict(
                    allow_execute=False,
                    issues=[
                        Issue(code="customer_ambiguous", block_level="session_block", message="还是没对上是哪家")
                    ],
                    reply_mode="ask",
                )
            self._orders.start_draft(session, chosen)
            return DecisionVerdict(allow_execute=True, reasons=["customer_disambiguated"])

        if act.type in {"set_line", "add_line"}:
            if session.draft.customer is None and session.pending_customer_candidates:
                session.line_buffer.append(act)
                return DecisionVerdict(
                    allow_execute=False,
                    issues=[Issue(code="customer_ambiguous", block_level="session_block", message="先确认是哪家再记货")],
                    reasons=["buffered_line"],
                )
            mention = self._resolve_product(session, str(act.slots.get("product_mention", "")))
            qty = Quantity(value=Decimal(act.slots.get("qty") or 1), uom=str(act.slots.get("uom") or self._default_uom(mention)))
            op = "add" if act.type == "add_line" else "set"
            line_verdict = self._policy.on_line(mention, expect_more=expect_more)
            if mention.matched_node is None:
                return line_verdict
            self._orders.apply_line(session, mention, qty, op)
            return line_verdict

        if act.type == "set_qty":
            line = self._target_line(session, act.slots.get("product_mention"))
            if line is None:
                return DecisionVerdict(
                    allow_execute=False,
                    issues=[Issue(code="no_focus_line", block_level="notice", message="改哪一行？")],
                )
            qty = Quantity(value=Decimal(act.slots.get("qty") or 0), uom=str(act.slots.get("uom") or line.qty.uom))
            mode = str(act.slots.get("mode") or "set")
            self._orders.set_qty(session, line, qty, mode)
            return DecisionVerdict(allow_execute=True, reasons=["qty_updated"])

        if act.type == "remove_line":
            mention = act.slots.get("product_mention")
            line = self._target_line(session, mention)
            if line is None:
                return DecisionVerdict(allow_execute=False, issues=[Issue(code="no_focus_line", block_level="notice")])
            dummy = line.mention
            self._orders.apply_line(session, dummy, line.qty, "remove")
            return DecisionVerdict(allow_execute=True, reasons=["line_removed"])

        if act.type == "confirm_order":
            return DecisionVerdict(allow_execute=True, reasons=["confirm_requested"])

        if act.type == "query_draft":
            return DecisionVerdict(allow_execute=True, reasons=["query"])

        return DecisionVerdict(allow_execute=False, reasons=["unknown_act"])

    def _resolve_product(self, session: SalesSession, raw: str) -> ProductMention:
        mention = self._ontology.lookup(raw)
        profile: CustomerProfile | None = None
        if session.draft.customer and session.draft.customer.id:
            profile = self._customers.get_profile(session.draft.customer.id)
        return self._policy.fill_sku(mention, profile)

    def _default_uom(self, mention: ProductMention) -> str:
        node = mention.resolved_sku or mention.matched_node
        return node.default_uom if node else "件"

    def _target_line(self, session: SalesSession, product_mention: object) -> object:
        if product_mention:
            mention = self._ontology.lookup(str(product_mention))
            node = mention.resolved_sku or mention.matched_node
            if node:
                for line in session.draft.lines:
                    other_id = line.product_sku_id or line.matched_node_id
                    if other_id is None:
                        continue
                    other = self._ontology.get(other_id)
                    if other and self._ontology.related(node, other):
                        return line
        if session.focus_line_id:
            for line in session.draft.lines:
                if line.line_id == session.focus_line_id:
                    return line
        return session.draft.lines[-1] if session.draft.lines else None

    def _reply(self, session: SalesSession, verdict: DecisionVerdict, *, expect_more: bool) -> str:
        blocks = [i for i in verdict.issues if i.block_level == "session_block"]
        if blocks and blocks[0].code == "customer_ambiguous":
            names = "、".join(o.get("name", "") for o in blocks[0].options)
            return f"有多家都叫这个，请问是哪一家？{names}"
        if session.draft.status == "confirmed":
            parts = [f"{self._line_name(ln)} {ln.qty.value}{ln.qty.uom}（价未定）" if ln.price.source == "tbd" else f"{self._line_name(ln)} {ln.qty.value}{ln.qty.uom}" for ln in session.draft.lines]
            who = session.draft.customer.name if session.draft.customer else ""
            return f"{who} 单已确认：" + "，".join(parts)
        if expect_more:
            return "记下了：" + "，".join(f"{self._line_name(ln)}{ln.qty.value}{ln.qty.uom}" for ln in session.draft.lines)
        parts = []
        for ln in session.draft.lines:
            extra = ""
            if ln.mention.filled_from == "profile" and ln.mention.resolved_sku:
                extra = f"（按档案{ln.mention.resolved_sku.name}）"
            price = "，价未定" if ln.price.source == "tbd" else ""
            parts.append(f"{self._line_name(ln)} {ln.qty.value}{ln.qty.uom}{extra}{price}")
        return "当前草稿：" + "；".join(parts) if parts else "还没有货"

    def _line_name(self, line) -> str:
        if line.mention.resolved_sku:
            return line.mention.resolved_sku.name
        if line.mention.matched_node:
            return line.mention.matched_node.name
        return line.mention.raw
