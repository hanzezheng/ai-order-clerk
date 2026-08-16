from __future__ import annotations

from app.agent.turn_parser import RuleTurnParser
from app.database.memory import InMemoryCatalog, InMemoryOrders, InMemorySessions
from app.entity.events import RecordingEventPublisher
from app.entity.session import SalesSession
from app.policy.decision import DecisionPolicy
from app.services.catalog_service import CustomerService, OntologyService
from app.services.order_service import OrderService
from app.session.runner import SalesSessionRunner


def build_world() -> tuple[SalesSessionRunner, RecordingEventPublisher, InMemoryCatalog]:
    catalog = InMemoryCatalog()
    sessions = InMemorySessions()
    orders = InMemoryOrders()
    events = RecordingEventPublisher()
    ontology = OntologyService(catalog)
    customers = CustomerService(catalog)
    order_service = OrderService(orders, ontology, events)
    policy = DecisionPolicy(ontology)
    runner = SalesSessionRunner(
        parser=RuleTurnParser(),
        policy=policy,
        customers=customers,
        ontology=ontology,
        orders=order_service,
        sessions=sessions,
    )
    return runner, events, catalog


def new_session() -> SalesSession:
    return SalesSession()
