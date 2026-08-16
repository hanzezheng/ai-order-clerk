from __future__ import annotations

from app.agent.parser import TurnParser
from app.agent.turn_parser import RuleTurnParser
from app.database.memory import InMemoryCatalog, InMemoryOrders, InMemorySessions
from app.entity.events import RecordingEventPublisher
from app.entity.session import SalesSession
from app.memory.extractor import MemoryExtractor
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
from app.session.runner import SalesSessionRunner


def build_world(parser: TurnParser | None = None) -> tuple[SalesSessionRunner, RecordingEventPublisher, InMemoryCatalog]:
    catalog = InMemoryCatalog()
    sessions = InMemorySessions()
    orders = InMemoryOrders()
    events = RecordingEventPublisher()
    ontology = OntologyService(catalog)
    customers = CustomerService(catalog)
    order_service = OrderService(orders, ontology, events)
    policy = DecisionPolicy(ontology)
    runner = SalesSessionRunner(
        parser=parser or RuleTurnParser(),
        policy=policy,
        customers=customers,
        ontology=ontology,
        resolver=ProductResolver(catalog, catalog.aliases),
        orders=order_service,
        sessions=sessions,
        memory_extractor=MemoryExtractor(),
        memory_policy=MemoryPolicy(),
        memory_service=MemoryService(catalog.aliases, catalog.prices),
        price_memory=PriceMemoryService(catalog.prices),
        response_generator=TemplateResponseGenerator(),
        reply_grounder=ReplyGrounder(),
        context_loader=ContextLoader(catalog, catalog.prices),
    )
    return runner, events, catalog


def new_session() -> SalesSession:
    return SalesSession()
