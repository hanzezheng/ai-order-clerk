from __future__ import annotations

from os import environ

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app.agent.parser import TurnParser
from app.agent.turn_parser import RuleTurnParser
from app.database.bundle import PersistenceBundle
from app.database.memory import (
    InMemoryCatalog,
    InMemoryEvidence,
    InMemoryIntakeReceipts,
    InMemoryOrders,
    InMemoryProcessedEvents,
    InMemorySessions,
    InMemoryTimeline,
    InMemoryWorkbench,
)
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
from app.services.ports import CatalogRepository, SessionRepository
from app.services.price_memory_service import PriceMemoryService
from app.services.product_resolver import ProductResolver
from app.session.intake import TurnIntake
from app.session.runner import SalesSessionRunner
from app.session.timeline import SessionTimelineStore
from app.workbench.service import WorkbenchService


@dataclass
class AppWorld:
    runner: SalesSessionRunner
    sessions: SessionRepository
    events: RecordingEventPublisher
    catalog: CatalogRepository
    timeline: SessionTimelineStore
    intake: TurnIntake
    workbench: WorkbenchService
    engine: Engine | None = None


def memory_bundle() -> PersistenceBundle:
    catalog = InMemoryCatalog()
    return PersistenceBundle(
        catalog=catalog,
        aliases=catalog.aliases,
        prices=catalog.prices,
        sessions=InMemorySessions(),
        orders=InMemoryOrders(),
        evidence=InMemoryEvidence(),
        timeline=InMemoryTimeline(),
        processed=InMemoryProcessedEvents(),
        workbench=InMemoryWorkbench(),
        receipts=InMemoryIntakeReceipts(),
    )


def assemble_world(
    bundle: PersistenceBundle,
    parser: TurnParser | None = None,
    *,
    engine: Engine | None = None,
) -> AppWorld:
    events = RecordingEventPublisher()
    timeline = SessionTimelineStore(bundle.timeline, bundle.processed)
    workbench = WorkbenchService(bundle.workbench)
    ontology = OntologyService(bundle.catalog)
    customers = CustomerService(bundle.catalog)
    order_service = OrderService(bundle.orders, ontology, events)
    evidence = EvidenceStore(bundle.evidence)
    extractor = MemoryExtractor(evidence=evidence, processed=bundle.processed, ontology=ontology)
    policy = DecisionPolicy(ontology)
    runner = SalesSessionRunner(
        parser=parser or RuleTurnParser(),
        policy=policy,
        customers=customers,
        ontology=ontology,
        resolver=ProductResolver(bundle.catalog, bundle.aliases),
        orders=order_service,
        sessions=bundle.sessions,
        memory_extractor=extractor,
        memory_policy=MemoryPolicy(),
        memory_service=MemoryService(bundle.aliases, bundle.prices, bundle.catalog),
        price_memory=PriceMemoryService(bundle.prices),
        response_generator=TemplateResponseGenerator(),
        reply_grounder=ReplyGrounder(),
        context_loader=ContextLoader(bundle.catalog, bundle.prices),
        events=events,
    )
    intake = TurnIntake(
        runner=runner,
        sessions=bundle.sessions,
        events=events,
        timeline=timeline,
        receipts=bundle.receipts,
        workbench=workbench,
    )
    return AppWorld(
        runner=runner,
        sessions=bundle.sessions,
        events=events,
        catalog=bundle.catalog,
        timeline=timeline,
        intake=intake,
        workbench=workbench,
        engine=engine,
    )


def build_app_world(
    parser: TurnParser | None = None,
    *,
    database_url: str | None = None,
    reset_schema: bool = False,
) -> AppWorld:
    url = database_url if database_url is not None else environ.get("DATABASE_URL")
    if url:
        from app.database.postgres.factory import create_postgres_engine, postgres_bundle, prepare_postgres

        engine = create_postgres_engine(url)
        prepare_postgres(engine, reset=reset_schema)
        return assemble_world(postgres_bundle(engine), parser, engine=engine)
    return assemble_world(memory_bundle(), parser)


def build_world(parser: TurnParser | None = None) -> tuple[SalesSessionRunner, RecordingEventPublisher, CatalogRepository]:
    world = build_app_world(parser)
    return world.runner, world.events, world.catalog


def new_session() -> SalesSession:
    return SalesSession()
