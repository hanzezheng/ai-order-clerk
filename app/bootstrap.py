from __future__ import annotations

from os import environ

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from app.agent.default_parser import build_default_parser
from app.agent.parser import TurnParser
from app.database.bundle import PersistenceBundle
from app.database.memory import (
    InMemoryCatalog,
    InMemoryEvidence,
    InMemoryIntakeReceipts,
    InMemoryOrders,
    InMemoryOutbox,
    InMemoryProcessedEvents,
    InMemorySessions,
    InMemoryTimeline,
    InMemoryWorkbench,
)
from app.database.uow import InMemoryUnitOfWork
from app.entity.events import RecordingEventPublisher
from app.entity.session import SalesSession
from app.events.consumers import MemoryConsumer, TimelineConsumer
from app.events.dispatcher import EventDispatcher
from app.events.gateway import TurnGateway
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
from app.services.ports import CatalogRepository, OutboxRepository, SessionRepository, UnitOfWork
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
    outbox: OutboxRepository
    engine: Engine | None = None


def memory_bundle(uow: InMemoryUnitOfWork | None = None) -> PersistenceBundle:
    catalog = InMemoryCatalog()
    processed = InMemoryProcessedEvents()
    unit = uow or InMemoryUnitOfWork()
    return PersistenceBundle(
        catalog=catalog,
        aliases=catalog.aliases,
        prices=catalog.prices,
        sessions=InMemorySessions(),
        orders=InMemoryOrders(),
        evidence=InMemoryEvidence(),
        timeline=InMemoryTimeline(),
        processed=processed,
        workbench=InMemoryWorkbench(),
        receipts=InMemoryIntakeReceipts(),
        outbox=InMemoryOutbox(unit, processed),
    )


def assemble_world(
    bundle: PersistenceBundle,
    parser: TurnParser | None = None,
    *,
    engine: Engine | None = None,
    uow: UnitOfWork | None = None,
) -> AppWorld:
    unit = uow or InMemoryUnitOfWork()
    timeline = SessionTimelineStore(bundle.timeline, bundle.processed)
    workbench = WorkbenchService(bundle.workbench)
    ontology = OntologyService(bundle.catalog)
    customers = CustomerService(bundle.catalog)
    evidence = EvidenceStore(bundle.evidence)
    extractor = MemoryExtractor(evidence=evidence, ontology=ontology)
    memory_policy = MemoryPolicy()
    memory_service = MemoryService(bundle.aliases, bundle.prices, bundle.catalog)
    dispatcher = EventDispatcher(
        uow=unit,
        outbox=bundle.outbox,
        sessions=bundle.sessions,
        consumers=[
            MemoryConsumer(
                extractor=extractor,
                policy=memory_policy,
                memory=memory_service,
                processed=bundle.processed,
            ),
            TimelineConsumer(timeline),
        ],
    )
    order_service = OrderService(bundle.orders, ontology, dispatcher)
    policy = DecisionPolicy(ontology)
    runner = SalesSessionRunner(
        parser=parser or build_default_parser(),
        policy=policy,
        customers=customers,
        ontology=ontology,
        resolver=ProductResolver(bundle.catalog, bundle.aliases),
        orders=order_service,
        sessions=bundle.sessions,
        memory_extractor=extractor,
        memory_policy=memory_policy,
        memory_service=memory_service,
        price_memory=PriceMemoryService(bundle.prices),
        response_generator=TemplateResponseGenerator(),
        reply_grounder=ReplyGrounder(),
        context_loader=ContextLoader(bundle.catalog, bundle.prices),
        events=dispatcher,
    )
    gateway = TurnGateway(runner, dispatcher)
    intake = TurnIntake(
        runner=gateway,
        sessions=bundle.sessions,
        timeline=timeline,
        receipts=bundle.receipts,
        workbench=workbench,
    )
    dispatcher.recover()
    return AppWorld(
        runner=gateway,  # type: ignore[arg-type]
        sessions=bundle.sessions,
        events=dispatcher,
        catalog=bundle.catalog,
        timeline=timeline,
        intake=intake,
        workbench=workbench,
        outbox=bundle.outbox,
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
        from app.database.postgres.sessioning import PostgresUnitOfWork

        engine = create_postgres_engine(url)
        prepare_postgres(engine, reset=reset_schema)
        uow = PostgresUnitOfWork(engine)
        return assemble_world(postgres_bundle(engine), parser, engine=engine, uow=uow)
    uow = InMemoryUnitOfWork()
    return assemble_world(memory_bundle(uow), parser, uow=uow)


def build_world(parser: TurnParser | None = None) -> tuple[SalesSessionRunner, RecordingEventPublisher, CatalogRepository]:
    world = build_app_world(parser)
    return world.runner, world.events, world.catalog


def new_session() -> SalesSession:
    return SalesSession()
