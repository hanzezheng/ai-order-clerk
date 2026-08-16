from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, exists, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm.attributes import flag_modified

from app.database.postgres.models import (
    CustomerProfileRow,
    CustomerRow,
    EvidenceRow,
    IntakeReceiptRow,
    IntakeSequenceRow,
    OrderLineRow,
    OrderRow,
    OutboxRow,
    PriceMemoryRow,
    ProcessedEventRow,
    ProductAliasRow,
    ProductNodeRow,
    SessionRow,
    TimelineRow,
    WorkbenchShiftRow,
)
from app.database.postgres.sessioning import finish_write, repo_session
from app.entity.catalog import CustomerProfile, CustomerRecord, ProductNode
from app.entity.events import OutboxRecord
from app.entity.intake import IntakeReceipt
from app.entity.memory import EvidenceRecord, PriceMemoryRecord
from app.entity.order import DraftOrder
from app.entity.session import SalesSession
from app.entity.timeline import TimelineEvent
from app.entity.workbench import WorkbenchShift, WorkbenchTaskRef
from app.services.ports import (
    AliasRepository,
    CatalogRepository,
    EvidenceRepository,
    IntakeReceiptRepository,
    OrderRepository,
    OutboxRepository,
    PriceMemoryRepository,
    ProcessedEventRepository,
    SessionRepository,
    TimelineRepository,
    WorkbenchRepository,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _node_from_row(row: ProductNodeRow) -> ProductNode:
    return ProductNode(
        id=row.id,
        parent_id=row.parent_id,
        level=row.level,  # type: ignore[arg-type]
        name=row.name,
        aliases=list(row.aliases or []),
        attributes=dict(row.attributes or {}),
        default_uom=row.default_uom,
        status=row.status,
    )


def _customer_from_row(row: CustomerRow) -> CustomerRecord:
    return CustomerRecord(
        id=row.id,
        legal_name=row.legal_name,
        display_name=row.display_name,
        stall_no=row.stall_no,
        phones=list(row.phones or []),
        aliases=list(row.aliases or []),
        status=row.status,
        confirm_count=row.confirm_count,
    )


def _profile_from_row(row: CustomerProfileRow) -> CustomerProfile:
    defaults: dict[str, UUID] = {}
    for key, value in (row.product_defaults or {}).items():
        defaults[str(key)] = value if isinstance(value, UUID) else UUID(str(value))
    return CustomerProfile(
        customer_id=row.customer_id,
        display_name=row.display_name,
        stall_no=row.stall_no,
        phones=list(row.phones or []),
        settlement_mode=row.settlement_mode,
        price_tier=row.price_tier,
        product_defaults=defaults,
        preferred_uoms=dict(row.preferred_uoms or {}),
    )


def _price_from_row(row: PriceMemoryRow) -> PriceMemoryRecord:
    return PriceMemoryRecord(
        price_type=row.price_type,  # type: ignore[arg-type]
        customer_id=row.customer_id,
        product_id=row.product_id,
        unit_price=row.unit_price,
        price_uom=row.price_uom,
        valid_until=row.valid_until,
        valid_from=row.valid_from,
        confidence=row.confidence,
        status=row.status,  # type: ignore[arg-type]
        last_confirmed_at=row.last_confirmed_at,
    )


class PostgresCatalog(CatalogRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self.aliases = PostgresAliasRepository(engine)
        self.prices = PostgresPriceRepository(engine)

    def list_customers(self) -> list[CustomerRecord]:
        with repo_session(self._engine) as db:
            rows = db.scalars(select(CustomerRow)).all()
            return [_customer_from_row(row) for row in rows]

    def get_customer(self, customer_id: UUID) -> CustomerRecord | None:
        with repo_session(self._engine) as db:
            row = db.get(CustomerRow, customer_id)
            return _customer_from_row(row) if row is not None else None

    def get_profile(self, customer_id: UUID) -> CustomerProfile | None:
        with repo_session(self._engine) as db:
            row = db.get(CustomerProfileRow, customer_id)
            return _profile_from_row(row) if row is not None else None

    def list_nodes(self) -> list[ProductNode]:
        with repo_session(self._engine) as db:
            rows = db.scalars(select(ProductNodeRow)).all()
            return [_node_from_row(row) for row in rows]

    def get_node(self, node_id: UUID) -> ProductNode | None:
        with repo_session(self._engine) as db:
            row = db.get(ProductNodeRow, node_id)
            return _node_from_row(row) if row is not None else None

    def put_customer(self, customer: CustomerRecord, profile: CustomerProfile) -> None:
        with repo_session(self._engine) as db:
            row = db.get(CustomerRow, customer.id)
            if row is None:
                db.add(
                    CustomerRow(
                        id=customer.id,
                        legal_name=customer.legal_name,
                        display_name=customer.display_name,
                        stall_no=customer.stall_no,
                        phones=list(customer.phones),
                        aliases=list(customer.aliases),
                        status=customer.status,
                        confirm_count=customer.confirm_count,
                    )
                )
            else:
                row.legal_name = customer.legal_name
                row.display_name = customer.display_name
                row.stall_no = customer.stall_no
                row.phones = list(customer.phones)
                row.aliases = list(customer.aliases)
                row.status = customer.status
                row.confirm_count = customer.confirm_count
            defaults = {str(k): str(v) for k, v in profile.product_defaults.items()}
            prow = db.get(CustomerProfileRow, profile.customer_id)
            if prow is None:
                db.add(
                    CustomerProfileRow(
                        customer_id=profile.customer_id,
                        display_name=profile.display_name,
                        stall_no=profile.stall_no,
                        phones=list(profile.phones),
                        settlement_mode=profile.settlement_mode,
                        price_tier=profile.price_tier,
                        product_defaults=defaults,
                        preferred_uoms=dict(profile.preferred_uoms),
                    )
                )
            else:
                prow.display_name = profile.display_name
                prow.stall_no = profile.stall_no
                prow.phones = list(profile.phones)
                prow.settlement_mode = profile.settlement_mode
                prow.price_tier = profile.price_tier
                prow.product_defaults = defaults
                prow.preferred_uoms = dict(profile.preferred_uoms)
                flag_modified(prow, "product_defaults")
                flag_modified(prow, "preferred_uoms")
            finish_write(db)

    def put_product_default(self, customer_id: UUID, node_id: UUID, sku_id: UUID) -> None:
        with repo_session(self._engine) as db:
            prow = db.get(CustomerProfileRow, customer_id)
            if prow is None:
                return
            defaults = dict(prow.product_defaults or {})
            defaults[str(node_id)] = str(sku_id)
            prow.product_defaults = defaults
            flag_modified(prow, "product_defaults")
            finish_write(db)


class PostgresAliasRepository(AliasRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def put(self, alias: str, node_id: UUID) -> None:
        with repo_session(self._engine) as db:
            row = db.get(ProductAliasRow, alias)
            if row is None:
                db.add(ProductAliasRow(alias=alias, node_id=node_id))
            else:
                row.node_id = node_id
            finish_write(db)

    def get(self, alias: str) -> UUID | None:
        with repo_session(self._engine) as db:
            row = db.get(ProductAliasRow, alias)
            return row.node_id if row is not None else None

    def snapshot(self) -> list[tuple[str, UUID]]:
        with repo_session(self._engine) as db:
            rows = db.scalars(select(ProductAliasRow)).all()
            return [(row.alias, row.node_id) for row in rows]


class PostgresPriceRepository(PriceMemoryRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def put(self, record: PriceMemoryRecord) -> None:
        with repo_session(self._engine) as db:
            existing = db.scalars(
                select(PriceMemoryRow).where(
                    PriceMemoryRow.price_type == record.price_type,
                    PriceMemoryRow.product_id == record.product_id,
                    PriceMemoryRow.customer_id.is_(record.customer_id)
                    if record.customer_id is None
                    else PriceMemoryRow.customer_id == record.customer_id,
                )
            ).all()
            for row in existing:
                db.delete(row)
            db.add(
                PriceMemoryRow(
                    id=uuid4(),
                    price_type=record.price_type,
                    customer_id=record.customer_id,
                    product_id=record.product_id,
                    unit_price=record.unit_price,
                    price_uom=record.price_uom,
                    valid_until=record.valid_until,
                    valid_from=record.valid_from,
                    confidence=record.confidence,
                    status=record.status,
                    last_confirmed_at=record.last_confirmed_at,
                )
            )
            finish_write(db)

    def snapshot(self) -> list[PriceMemoryRecord]:
        with repo_session(self._engine) as db:
            rows = db.scalars(select(PriceMemoryRow)).all()
            return [_price_from_row(row) for row in rows]


class PostgresEvidenceRepository(EvidenceRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(
        self,
        *,
        customer_id: UUID,
        kind: str,
        node_id: UUID,
        sku_id: UUID,
    ) -> EvidenceRecord | None:
        with repo_session(self._engine) as db:
            row = db.get(EvidenceRow, (customer_id, kind, node_id, sku_id))
            if row is None:
                return None
            return EvidenceRecord(
                customer_id=row.customer_id,
                kind=row.kind,
                node_id=row.node_id,
                sku_id=row.sku_id,
                count=row.count,
                positive_count=row.positive_count,
                negative_count=row.negative_count,
                status=row.status,  # type: ignore[arg-type]
                last_confirmed_at=row.last_confirmed_at,
            )

    def put(self, record: EvidenceRecord) -> None:
        with repo_session(self._engine) as db:
            row = db.get(
                EvidenceRow, (record.customer_id, record.kind, record.node_id, record.sku_id)
            )
            if row is None:
                db.add(
                    EvidenceRow(
                        customer_id=record.customer_id,
                        kind=record.kind,
                        node_id=record.node_id,
                        sku_id=record.sku_id,
                        count=record.count,
                        positive_count=record.positive_count,
                        negative_count=record.negative_count,
                        status=record.status,
                        last_confirmed_at=record.last_confirmed_at,
                    )
                )
            else:
                row.count = record.count
                row.positive_count = record.positive_count
                row.negative_count = record.negative_count
                row.status = record.status
                row.last_confirmed_at = record.last_confirmed_at
            finish_write(db)


class PostgresSessionRepository(SessionRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, session_id: UUID) -> SalesSession | None:
        with repo_session(self._engine) as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                return None
            return SalesSession.model_validate(row.payload)

    def save(self, session: SalesSession) -> None:
        payload = session.model_dump(mode="json")
        with repo_session(self._engine) as db:
            row = db.get(SessionRow, session.session_id)
            if row is None:
                db.add(
                    SessionRow(
                        session_id=session.session_id,
                        status=session.status,
                        payload=payload,
                        updated_at=_now(),
                    )
                )
            else:
                row.status = session.status
                row.payload = payload
                row.updated_at = _now()
                flag_modified(row, "payload")
            finish_write(db)


class PostgresOrderRepository(OrderRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save_draft(self, draft: DraftOrder) -> None:
        payload = draft.model_dump(mode="json")
        customer_id = draft.customer.id if draft.customer is not None else None
        with repo_session(self._engine) as db:
            row = db.get(OrderRow, draft.order_id)
            if row is None:
                db.add(
                    OrderRow(
                        order_id=draft.order_id,
                        status=draft.status,
                        customer_id=customer_id,
                        payload=payload,
                        updated_at=_now(),
                    )
                )
                db.flush()
            else:
                row.status = draft.status
                row.customer_id = customer_id
                row.payload = payload
                row.updated_at = _now()
                flag_modified(row, "payload")
            db.execute(delete(OrderLineRow).where(OrderLineRow.order_id == draft.order_id))
            for line in draft.lines:
                db.add(
                    OrderLineRow(
                        line_id=line.line_id,
                        order_id=draft.order_id,
                        sku_id=line.product_sku_id,
                        qty=line.qty.value,
                        uom=line.qty.uom,
                        price_source=line.price.source,
                        unit_price=line.price.unit_price,
                        line_status=line.line_status,
                    )
                )
            finish_write(db)

    def get_draft(self, order_id: UUID) -> DraftOrder | None:
        with repo_session(self._engine) as db:
            row = db.get(OrderRow, order_id)
            if row is None:
                return None
            return DraftOrder.model_validate(row.payload)


class PostgresTimelineRepository(TimelineRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def list(self, session_id: UUID) -> list[TimelineEvent]:
        with repo_session(self._engine) as db:
            rows = db.scalars(
                select(TimelineRow)
                .where(TimelineRow.session_id == session_id)
                .order_by(TimelineRow.occurred_at, TimelineRow.event_id)
            ).all()
            return [
                TimelineEvent(
                    event_id=row.event_id,
                    session_id=row.session_id,
                    event_type=row.event_type,
                    occurred_at=row.occurred_at,
                    payload=dict(row.payload or {}),
                )
                for row in rows
            ]

    def append(self, event: TimelineEvent) -> TimelineEvent:
        stored = event.model_copy(deep=True)
        with repo_session(self._engine) as db:
            db.add(
                TimelineRow(
                    event_id=stored.event_id,
                    session_id=stored.session_id,
                    event_type=stored.event_type,
                    occurred_at=stored.occurred_at,
                    payload=dict(stored.payload),
                )
            )
            finish_write(db)
        return stored


class PostgresProcessedEvents(ProcessedEventRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def has(self, consumer: str, event_id: UUID) -> bool:
        with repo_session(self._engine) as db:
            return db.get(ProcessedEventRow, (consumer, event_id)) is not None

    def mark(self, consumer: str, event_id: UUID) -> None:
        with repo_session(self._engine) as db:
            if db.get(ProcessedEventRow, (consumer, event_id)) is None:
                db.add(ProcessedEventRow(consumer=consumer, event_id=event_id))
                finish_write(db)


class PostgresWorkbenchRepository(WorkbenchRepository):
    SHIFT_ID = 1

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_shift(self) -> WorkbenchShift:
        with repo_session(self._engine) as db:
            row = db.get(WorkbenchShiftRow, self.SHIFT_ID)
            if row is None:
                return WorkbenchShift()
            tasks = [WorkbenchTaskRef.model_validate(item) for item in (row.tasks or [])]
            return WorkbenchShift(
                business_date=row.business_date,
                current_session_id=row.current_session_id,
                tasks=tasks,
            )

    def save_shift(self, shift: WorkbenchShift) -> None:
        tasks = [item.model_dump(mode="json") for item in shift.tasks]
        with repo_session(self._engine) as db:
            row = db.get(WorkbenchShiftRow, self.SHIFT_ID)
            if row is None:
                db.add(
                    WorkbenchShiftRow(
                        id=self.SHIFT_ID,
                        business_date=shift.business_date,
                        current_session_id=shift.current_session_id,
                        tasks=tasks,
                    )
                )
            else:
                row.business_date = shift.business_date
                row.current_session_id = shift.current_session_id
                row.tasks = tasks
                flag_modified(row, "tasks")
            finish_write(db)


class PostgresIntakeReceipts(IntakeReceiptRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, session_id: UUID, utterance_id: str) -> IntakeReceipt | None:
        with repo_session(self._engine) as db:
            row = db.scalars(
                select(IntakeReceiptRow).where(
                    IntakeReceiptRow.session_id == session_id,
                    IntakeReceiptRow.utterance_id == utterance_id,
                )
            ).first()
            if row is None:
                return None
            return IntakeReceipt(
                session_id=row.session_id,
                utterance_id=row.utterance_id,
                payload=dict(row.payload),
            )

    def put(self, receipt: IntakeReceipt) -> None:
        with repo_session(self._engine) as db:
            row = db.scalars(
                select(IntakeReceiptRow).where(
                    IntakeReceiptRow.session_id == receipt.session_id,
                    IntakeReceiptRow.utterance_id == receipt.utterance_id,
                )
            ).first()
            if row is None:
                db.add(
                    IntakeReceiptRow(
                        session_id=receipt.session_id,
                        utterance_id=receipt.utterance_id,
                        payload=dict(receipt.payload),
                    )
                )
            else:
                row.payload = dict(receipt.payload)
                flag_modified(row, "payload")
            finish_write(db)

    def last_seq(self, session_id: UUID) -> int | None:
        with repo_session(self._engine) as db:
            row = db.get(IntakeSequenceRow, session_id)
            return row.last_seq if row is not None else None

    def set_last_seq(self, session_id: UUID, seq: int) -> None:
        with repo_session(self._engine) as db:
            row = db.get(IntakeSequenceRow, session_id)
            if row is None:
                db.add(IntakeSequenceRow(session_id=session_id, last_seq=seq))
            else:
                row.last_seq = seq
            finish_write(db)


class PostgresOutboxRepository(OutboxRepository):
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def append(self, record: OutboxRecord) -> None:
        stored = record.model_copy(deep=True)
        with repo_session(self._engine) as db:
            if db.get(OutboxRow, stored.event_id) is not None:
                finish_write(db)
                return
            db.add(
                OutboxRow(
                    event_id=stored.event_id,
                    event_type=stored.event_type,
                    aggregate_type=stored.aggregate_type,
                    aggregate_id=stored.aggregate_id,
                    session_id=stored.session_id,
                    payload=dict(stored.payload),
                    occurred_at=stored.occurred_at,
                    recorded_at=stored.recorded_at,
                )
            )
            finish_write(db)

    def get(self, event_id: UUID) -> OutboxRecord | None:
        with repo_session(self._engine) as db:
            row = db.get(OutboxRow, event_id)
            return _outbox_from_row(row) if row is not None else None

    def list_pending(
        self,
        consumer: str,
        *,
        event_types: tuple[str, ...] | None = None,
        limit: int = 500,
    ) -> list[OutboxRecord]:
        with repo_session(self._engine) as db:
            stmt = (
                select(OutboxRow)
                .where(
                    ~exists(
                        select(ProcessedEventRow.event_id).where(
                            ProcessedEventRow.consumer == consumer,
                            ProcessedEventRow.event_id == OutboxRow.event_id,
                        )
                    )
                )
                .order_by(OutboxRow.recorded_at, OutboxRow.event_id)
                .limit(limit)
            )
            if event_types is not None:
                stmt = stmt.where(OutboxRow.event_type.in_(event_types))
            return [_outbox_from_row(row) for row in db.scalars(stmt).all()]


def _outbox_from_row(row: OutboxRow) -> OutboxRecord:
    return OutboxRecord(
        event_id=row.event_id,
        event_type=row.event_type,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        session_id=row.session_id,
        payload=dict(row.payload or {}),
        occurred_at=row.occurred_at,
        recorded_at=row.recorded_at,
    )
