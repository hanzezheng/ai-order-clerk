from __future__ import annotations

from dataclasses import dataclass

from app.agent.parser import TurnParser
from app.agent.turn_parser import RuleTurnParser
from app.database.memory import InMemoryCatalog, InMemoryOrders, InMemorySessions
from app.entity.events import RecordingEventPublisher
from app.entity.session import SalesSession
from app.memory.extractor import MemoryExtractor
from app.memory.evidence import EvidenceStore
from app.memory.policy import MemoryPolicy
from app.policy.decision import DecisionPolicy
from app.response.grounder import ReplyGrounder
from app.response.template import TemplateResponseGenerator
from app.services.catalog_service import CustomerService, OntologyService
from app.services.context_loader import ContextLoader
from app.services.memory_service import MemoryService
from app.services.order_service import OrderService
from app.services.price_memory_service import PriceMemoryService
from app.services.product_resolver import ProductResolver
from app.session.intake import TurnIntake
from app.session.runner import SalesSessionRunner
from app.session.timeline import SessionTimelineStore


@dataclass
class AppWorld:
    runner: SalesSessionRunner
    sessions: InMemorySessions
    events: RecordingEventPublisher
    catalog: InMemoryCatalog
    timeline: SessionTimelineStore
    intake: TurnIntake


def build_app_world(parser: TurnParser | None = None) -> AppWorld:
    catalog = InMemoryCatalog()
    sessions = InMemorySessions()
    orders = InMemoryOrders()
    events = RecordingEventPublisher()
    timeline = SessionTimelineStore()
    ontology = OntologyService(catalog)
    customers = CustomerService(catalog)
    order_service = OrderService(orders, ontology, events)
    evidence = EvidenceStore()
    extractor = MemoryExtractor(evidence=evidence, ontology=ontology)
    policy = DecisionPolicy(ontology)
    runner = SalesSessionRunner(
        parser=parser or RuleTurnParser(),
        policy=policy,
        customers=customers,
        ontology=ontology,
        resolver=ProductResolver(catalog, catalog.aliases),
        orders=order_service,
        sessions=sessions,
        memory_extractor=extractor,
        memory_policy=MemoryPolicy(),
        memory_service=MemoryService(catalog.aliases, catalog.prices, catalog),
        price_memory=PriceMemoryService(catalog.prices),
        response_generator=TemplateResponseGenerator(),
        reply_grounder=ReplyGrounder(),
        context_loader=ContextLoader(catalog, catalog.prices),
        events=events,
    )
    intake = TurnIntake(runner=runner, sessions=sessions, events=events, timeline=timeline)
    return AppWorld(
        runner=runner,
        sessions=sessions,
        events=events,
        catalog=catalog,
        timeline=timeline,
        intake=intake,
    )


def build_world(parser: TurnParser | None = None) -> tuple[SalesSessionRunner, RecordingEventPublisher, InMemoryCatalog]:
    world = build_app_world(parser)
    return world.runner, world.events, world.catalog


def new_session() -> SalesSession:
    return SalesSession()
