from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from app.entity.catalog import CustomerProfile, ProductMention
from app.entity.events import PREFERENCE_ADJUSTED, DomainEvent, DomainEventPublisher
from app.entity.issue import DecisionVerdict, Issue
from app.entity.order import Quantity
from app.entity.price import PriceQuote
from app.entity.session import PendingCustomerCreate, SalesSession, TurnResult
from app.entity.speech import SpeechAct
from app.agent.parser import TurnParser
from app.memory.extractor import MemoryExtractor
from app.memory.policy import MemoryPolicy
from app.policy.decision import DecisionPolicy
from app.response.grounder import ReplyGrounder
from app.response.planner import build_reply_plan
from app.response.template import TemplateResponseGenerator
from app.services.catalog_service import CustomerService, OntologyService, parse_distinguisher
from app.services.context_loader import ContextLoader
from app.services.memory_service import MemoryService
from app.services.order_service import OrderService
from app.services.price_memory_service import PriceMemoryService
from app.services.product_resolver import ProductResolver
from app.services.product_understanding import ProductUnderstanding
from app.services.ports import SessionRepository


class SalesSessionRunner:
    """parse → resolve → policy → service → extract → memory policy → memory service。"""

    def __init__(
        self,
        *,
        parser: TurnParser,
        policy: DecisionPolicy,
        customers: CustomerService,
        ontology: OntologyService,
        resolver: ProductResolver,
        orders: OrderService,
        sessions: SessionRepository,
        memory_extractor: MemoryExtractor,
        memory_policy: MemoryPolicy,
        memory_service: MemoryService,
        price_memory: PriceMemoryService,
        response_generator: TemplateResponseGenerator | None = None,
        reply_grounder: ReplyGrounder | None = None,
        context_loader: ContextLoader | None = None,
        events: DomainEventPublisher | None = None,
        product_understanding: ProductUnderstanding | None = None,
    ) -> None:
        self._parser = parser
        self._policy = policy
        self._customers = customers
        self._ontology = ontology
        self._resolver = resolver
        self._orders = orders
        self._sessions = sessions
        self._memory_extractor = memory_extractor
        self._memory_policy = memory_policy
        self._memory_service = memory_service
        self._price_memory = price_memory
        self._response = response_generator or TemplateResponseGenerator()
        self._grounder = reply_grounder or ReplyGrounder()
        self._context_loader = context_loader
        self._events = events
        self._understanding = product_understanding or ProductUnderstanding()

    def handle(self, session: SalesSession, text: str, *, expect_more: bool = False) -> TurnResult:
        session.turn_index += 1
        parsed = self._parser.parse(text)
        acts = list(parsed.acts)
        awaiting_customer = bool(session.pending_customer_candidates) or session.pending_customer_create is not None
        if awaiting_customer and not (acts and acts[0].type == "start_order"):
            extras = [
                a
                for a in acts
                if a.type in {"set_line", "add_line", "set_qty", "set_price", "remove_line"}
            ]
            acts = [SpeechAct(type="clarify", slots={"mention": text})] + extras

        all_issues: list[Issue] = []
        reasons: list[str] = []
        executed: list[str] = []
        changed_line_ids: list = []
        last_verdict = DecisionVerdict()

        for act in acts:
            last_verdict = self._apply(session, act, expect_more=expect_more)
            all_issues.extend(last_verdict.issues)
            reasons.extend(last_verdict.reasons)
            if last_verdict.allow_execute:
                executed.append(act.type)
                if act.type in {"set_line", "add_line", "set_qty", "set_price", "refine_spec"}:
                    if session.focus_line_id and session.focus_line_id not in changed_line_ids:
                        changed_line_ids.append(session.focus_line_id)

        confirm_ok = False
        if any(a.type == "confirm_order" for a in acts):
            gate = self._policy.confirm_gate(session)
            all_issues.extend(gate.issues)
            confirm_ok = gate.confirm_ok
            if gate.confirm_ok:
                self._orders.confirm(session)
                executed.append("confirm_order")
                self._publish_preference_adjusted(session)
                self._observe_customer(session)
            reasons.extend(gate.reasons)

        if self._context_loader is not None:
            context = self._context_loader.load(session)
            notice_issues = self._policy.collect_notices(session, context)
            all_issues.extend(notice_issues)
            reasons.extend(i.code for i in notice_issues)

        if any(i.block_level == "session_block" for i in all_issues):
            reply_mode = "ask"
        elif session.draft.status == "confirmed":
            reply_mode = "recap"
        elif expect_more:
            reply_mode = "ack"
        else:
            reply_mode = "recap"

        verdict = DecisionVerdict(
            allow_execute=True,
            issues=all_issues,
            confirm_ok=confirm_ok,
            reasons=reasons,
            reply_mode=reply_mode,
        )
        session.deferred_issues = [i for i in all_issues if i.ask_when == "idle"]
        plan = build_reply_plan(session, verdict, changed_line_ids=changed_line_ids)
        reply_text = self._response.generate(plan)
        grounded = self._grounder.check(reply_text, plan)
        fallback_reason = None
        if not grounded.ok:
            reply_text = self._response.generate(plan)
            fallback_reason = "grounding_violation"
        self._sessions.save(session)
        return TurnResult(
            reply_text=reply_text,
            session=session,
            verdict=verdict,
            acts=acts,
            commands_executed=executed,
            generator_name="template",
            reply_fallback_reason=fallback_reason,
            reply_plan=plan,
        )

    def _apply(self, session: SalesSession, act: SpeechAct, *, expect_more: bool) -> DecisionVerdict:
        if act.type == "start_order":
            ref = self._customers.lookup(str(act.slots.get("customer_mention", "")))
            verdict = self._policy.on_start_order(ref)
            if not verdict.allow_execute:
                session.pending_customer_candidates = ref.candidates
                if ref.needs_distinguisher or not ref.candidates:
                    session.pending_customer_create = PendingCustomerCreate(mention=ref.name)
                return verdict
            assert ref.id is not None
            session.pending_customer_create = None
            session.pending_customer_candidates = []
            self._orders.start_draft(session, ref)
            return verdict

        if act.type == "clarify":
            mention = str(act.slots.get("mention") or act.span or "")
            chosen = self._customers.match_candidate(mention, session.pending_customer_candidates)
            if chosen is None and session.pending_customer_create is not None:
                stall, phone = parse_distinguisher(mention)
                chosen = self._customers.create_candidate(
                    session.pending_customer_create.mention,
                    stall_no=stall,
                    phone_tail=phone,
                )
            if chosen is None:
                return DecisionVerdict(
                    allow_execute=False,
                    issues=[
                        Issue(
                            code="customer_unknown" if session.pending_customer_create else "customer_ambiguous",
                            block_level="session_block",
                            message="还是没对上是哪家",
                        )
                    ],
                    reply_mode="ask",
                )
            session.pending_customer_create = None
            session.pending_customer_candidates = []
            self._orders.start_draft(session, chosen)
            return DecisionVerdict(allow_execute=True, reasons=["customer_disambiguated"])

        if act.type in {"set_line", "add_line"}:
            if session.draft.customer is None and (
                session.pending_customer_candidates or session.pending_customer_create is not None
            ):
                session.line_buffer.append(act)
                return DecisionVerdict(
                    allow_execute=False,
                    issues=[Issue(code="customer_ambiguous", block_level="session_block", message="先确认是哪家再记货")],
                    reasons=["buffered_line"],
                )
            mention = self._resolve_product(session, act)
            qty = Quantity(value=Decimal(act.slots.get("qty") or 1), uom=str(act.slots.get("uom") or self._default_uom(mention)))
            op = "add" if act.type == "add_line" else "set"
            line_verdict = self._policy.on_line(mention, expect_more=expect_more)
            if mention.matched_node is None:
                return line_verdict
            self._orders.apply_line(session, mention, qty, op)
            self._suppress_profile_default_if_needed(session)
            return line_verdict

        if act.type == "set_price":
            if session.draft.customer is None:
                return DecisionVerdict(
                    allow_execute=False,
                    issues=[Issue(code="customer_missing", block_level="session_block", message="还没开谁的单")],
                    reasons=["unbound_customer"],
                )
            mention = self._resolve_product(session, act)
            verdict = self._policy.on_set_price(mention)
            if not verdict.allow_execute:
                return verdict
            quote = PriceQuote(
                unit_price=Decimal(str(act.slots.get("unit_price"))),
                price_uom=str(act.slots.get("price_uom") or "块"),
                source="explicit",
            )
            self._orders.set_price(session, mention, quote)
            self._suppress_profile_default_if_needed(session)
            return verdict

        if act.type == "refine_spec":
            mention = self._resolve_product(session, act)
            line = self._target_line(
                session, act.slots.get("product_mention") or act.slots.get("spec_mention")
            )
            if line is None or mention.matched_node is None:
                return DecisionVerdict(
                    allow_execute=False,
                    issues=[Issue(code="no_focus_line", block_level="notice", message="改哪一行？")],
                )
            self._orders.apply_line(session, mention, line.qty, "set")
            self._suppress_profile_default_if_needed(session)
            return DecisionVerdict(allow_execute=True, reasons=["spec_refined"])

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

    def _resolve_product(self, session: SalesSession, act: SpeechAct) -> ProductMention:
        product_mention = str(act.slots.get("product_mention") or "")
        spec = act.slots.get("spec_mention")
        spec_mention = str(spec) if spec else None
        focus_id = None
        if act.type == "refine_spec" or (spec_mention and not product_mention):
            line = self._target_line(session, product_mention or spec_mention)
            if line is not None:
                focus_id = line.product_sku_id or line.matched_node_id
        query = self._understanding.interpret(
            product_mention=product_mention,
            spec_mention=spec_mention,
            focus_node_id=focus_id,
        )
        mention = self._resolver.resolve_query(query)
        profile: CustomerProfile | None = None
        if session.draft.customer and session.draft.customer.id:
            profile = self._customers.get_profile(session.draft.customer.id)
        filled = self._policy.fill_sku(
            mention,
            profile,
            suppressed_node_ids=session.suppressed_default_node_ids,
        )
        if filled.matched_node is None:
            filled.status = "candidate"
            self._record_mention_candidate(session, filled)
        customer_id = session.draft.customer.id if session.draft.customer else None
        sku = filled.resolved_sku
        if sku is not None and customer_id is not None:
            lookup = self._price_memory.lookup(customer_id=customer_id, product_id=sku.id)
            if self._price_memory.silent_quote(lookup) is None:
                pass
        return filled

    def _suppress_profile_default_if_needed(self, session: SalesSession) -> None:
        customer = session.draft.customer
        if customer is None or customer.id is None:
            return
        profile = self._customers.get_profile(customer.id)
        if profile is None:
            return
        for line in session.draft.lines:
            if line.product_sku_id is None:
                continue
            node_id = self._line_preference_node_id(line)
            if node_id is None:
                continue
            default_sku = profile.product_defaults.get(str(node_id))
            if default_sku is None or default_sku == line.product_sku_id:
                continue
            if node_id not in session.suppressed_default_node_ids:
                session.suppressed_default_node_ids.append(node_id)

    def _publish_preference_adjusted(self, session: SalesSession) -> None:
        if self._events is None:
            return
        customer = session.draft.customer
        if customer is None or customer.id is None:
            return
        profile = self._customers.get_profile(customer.id)
        if profile is None:
            return
        for line in session.draft.lines:
            if line.product_sku_id is None:
                continue
            node_id = self._line_preference_node_id(line)
            if node_id is None:
                continue
            from_sku = profile.product_defaults.get(str(node_id))
            if from_sku is None or from_sku == line.product_sku_id:
                continue
            self._events.publish(
                DomainEvent(
                    event_type=PREFERENCE_ADJUSTED,
                    aggregate_id=session.draft.order_id,
                    payload={
                        "customer_id": str(customer.id),
                        "node_id": str(node_id),
                        "from_sku_id": str(from_sku),
                        "to_sku_id": str(line.product_sku_id),
                        "order_id": str(session.draft.order_id),
                    },
                )
            )

    def _line_preference_node_id(self, line) -> UUID | None:
        node = line.mention.resolved_sku or line.mention.matched_node
        if node is None:
            return line.matched_node_id
        variety = self._ontology.variety_id(node)
        if variety is not None:
            return variety
        if line.mention.matched_node is not None:
            return line.mention.matched_node.id
        return line.matched_node_id

    def _observe_customer(self, session: SalesSession) -> None:
        customer = session.draft.customer
        if customer is None or customer.id is None:
            return
        self._customers.record_confirm(customer.id)

    def _record_mention_candidate(self, session: SalesSession, mention: ProductMention) -> None:
        raw = (mention.raw or "").strip()
        if not raw:
            return
        if any(item.raw == raw for item in session.product_mention_candidates):
            return
        session.product_mention_candidates.append(mention.model_copy(deep=True))

    def _default_uom(self, mention: ProductMention) -> str:
        node = mention.resolved_sku or mention.matched_node
        return node.default_uom if node else "件"

    def _target_line(self, session: SalesSession, product_mention: object):
        if product_mention:
            mention = self._resolver.resolve(str(product_mention))
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
