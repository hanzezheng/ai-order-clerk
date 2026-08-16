from __future__ import annotations

from uuid import UUID

from app.entity.events import DomainEvent, OutboxRecord, RecordingEventPublisher, aggregate_type_for
from app.entity.session import SalesSession
from app.entity.timeline import sanitize_timeline_payload
from app.services.ports import OutboxRepository, SessionRepository, UnitOfWork


class EventConsumer:
    name: str
    event_types: tuple[str, ...] | None = None

    def consume(self, session: SalesSession | None, event: DomainEvent) -> None:
        raise NotImplementedError


class EventDispatcher(RecordingEventPublisher):
    """装配层：publish 入 Outbox；drain 按 consumer 投递。业务只见 publish。"""

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        outbox: OutboxRepository,
        sessions: SessionRepository,
        consumers: list[EventConsumer],
    ) -> None:
        super().__init__()
        self._uow = uow
        self._outbox = outbox
        self._sessions = sessions
        self._consumers = consumers
        self._session_id: UUID | None = None

    def begin_turn(self, session: SalesSession) -> None:
        self._session_id = session.session_id
        self._uow.begin()

    def finish_turn(self, session: SalesSession) -> None:
        self._uow.commit()
        self._session_id = None
        self.drain(session)

    def abort_turn(self) -> None:
        self._uow.rollback()
        self._session_id = None

    def publish(self, event: DomainEvent) -> None:
        super().publish(event)
        payload = sanitize_timeline_payload(dict(event.payload or {}))
        session_id = self._session_id or _as_uuid((event.payload or {}).get("session_id"))
        if session_id is not None and "session_id" not in payload:
            payload["session_id"] = str(session_id)
        self._outbox.append(
            OutboxRecord(
                event_id=event.event_id,
                event_type=event.event_type,
                aggregate_type=aggregate_type_for(event.event_type),
                aggregate_id=event.aggregate_id,
                session_id=session_id,
                payload=payload,
                occurred_at=event.occurred_at,
            )
        )

    def drain(self, session: SalesSession | None = None) -> None:
        for consumer in self._consumers:
            pending = self._outbox.list_pending(consumer.name, event_types=consumer.event_types)
            for record in pending:
                live = session
                if record.session_id is not None and (live is None or live.session_id != record.session_id):
                    live = self._sessions.get(record.session_id)
                self._uow.begin()
                try:
                    consumer.consume(live, record.to_event())
                    self._uow.commit()
                except Exception:
                    self._uow.rollback()
                    raise

    def recover(self) -> None:
        self.drain(session=None)


def _as_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
