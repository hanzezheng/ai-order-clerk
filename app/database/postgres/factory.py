from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.database.bundle import PersistenceBundle
from app.database.postgres.models import Base
from app.database.postgres.repos import (
    PostgresCatalog,
    PostgresEvidenceRepository,
    PostgresIntakeReceipts,
    PostgresOrderRepository,
    PostgresOutboxRepository,
    PostgresProcessedEvents,
    PostgresSessionRepository,
    PostgresTimelineRepository,
    PostgresWorkbenchRepository,
)
from app.database.postgres.seed import seed_catalog


def create_postgres_engine(url: str) -> Engine:
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    elif url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    return create_engine(url, pool_pre_ping=True, future=True)


def prepare_postgres(engine: Engine, *, reset: bool = False) -> None:
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed_catalog(engine)


def postgres_bundle(engine: Engine) -> PersistenceBundle:
    catalog = PostgresCatalog(engine)
    return PersistenceBundle(
        catalog=catalog,
        aliases=catalog.aliases,
        prices=catalog.prices,
        sessions=PostgresSessionRepository(engine),
        orders=PostgresOrderRepository(engine),
        evidence=PostgresEvidenceRepository(engine),
        timeline=PostgresTimelineRepository(engine),
        processed=PostgresProcessedEvents(engine),
        workbench=PostgresWorkbenchRepository(engine),
        receipts=PostgresIntakeReceipts(engine),
        outbox=PostgresOutboxRepository(engine),
    )
