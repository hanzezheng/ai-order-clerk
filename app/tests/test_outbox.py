from __future__ import annotations

from uuid import uuid4

from app.bootstrap import build_app_world, new_session
from app.database.memory import APPLE, FUJI80, LI_BOSS, InMemoryOutbox, InMemoryProcessedEvents
from app.database.uow import InMemoryUnitOfWork
from app.entity.events import ORDER_CONFIRMED, OutboxRecord, aggregate_type_for
from app.services.ports import MEMORY_EXTRACTOR_CONSUMER, TIMELINE_CONSUMER
from app.tests.pgutil import postgres_url_or_skip


def _record(*, event_type: str = ORDER_CONFIRMED) -> OutboxRecord:
    event_id = uuid4()
    aggregate_id = uuid4()
    return OutboxRecord(
        event_id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type_for(event_type),
        aggregate_id=aggregate_id,
        session_id=uuid4(),
        payload={"session_id": str(uuid4())},
    )


def _evidence(world, *, customer_id=LI_BOSS, node_id=APPLE, sku_id=FUJI80):
    return world.runner._memory_extractor._evidence._repo.get(
        customer_id=customer_id,
        kind="product_default",
        node_id=node_id,
        sku_id=sku_id,
    )


def _confirm_li_fuji(world):
    session = new_session()
    world.sessions.save(session)
    world.runner.handle(session, "开李老板的单")
    world.runner.handle(session, "苹果60件")
    done = world.runner.handle(session, "好了")
    assert done.verdict.confirm_ok is True
    return done.session


def test_outbox_pending_hidden_until_commit_and_isolated_by_consumer():
    uow = InMemoryUnitOfWork()
    processed = InMemoryProcessedEvents()
    outbox = InMemoryOutbox(uow, processed)
    record = _record()
    uow.begin()
    outbox.append(record)
    assert outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER) == []
    assert outbox.get(record.event_id) is not None
    uow.commit()
    pending = outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER)
    assert [item.event_id for item in pending] == [record.event_id]
    processed.mark(MEMORY_EXTRACTOR_CONSUMER, record.event_id)
    assert outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER) == []
    leftover = outbox.list_pending(TIMELINE_CONSUMER)
    assert [item.event_id for item in leftover] == [record.event_id]


def test_outbox_rollback_discards_staged_record():
    uow = InMemoryUnitOfWork()
    processed = InMemoryProcessedEvents()
    outbox = InMemoryOutbox(uow, processed)
    record = _record()
    uow.begin()
    outbox.append(record)
    uow.rollback()
    assert outbox.get(record.event_id) is None
    assert outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER) == []


def test_confirm_writes_outbox_and_consumers_mark_separately():
    world = build_app_world()
    session = _confirm_li_fuji(world)
    confirmed = [event for event in world.events.events if event.event_type == ORDER_CONFIRMED]
    assert len(confirmed) == 1
    event_id = confirmed[0].event_id
    stored = world.outbox.get(event_id)
    assert stored is not None
    assert stored.event_type == ORDER_CONFIRMED
    assert stored.session_id == session.session_id
    processed = world.events._consumers[0]._processed
    assert processed.has(MEMORY_EXTRACTOR_CONSUMER, event_id) is True
    assert processed.has(TIMELINE_CONSUMER, event_id) is True
    assert (
        world.outbox.list_pending(
            MEMORY_EXTRACTOR_CONSUMER,
            event_types=(ORDER_CONFIRMED,),
        )
        == []
    )
    assert world.outbox.list_pending(TIMELINE_CONSUMER) == []
    assert any(item.event_type == ORDER_CONFIRMED for item in world.timeline.list(session.session_id))
    evidence = _evidence(world)
    assert evidence is not None
    assert evidence.count == 1


def test_drain_twice_does_not_double_evidence():
    world = build_app_world()
    session = _confirm_li_fuji(world)
    first = _evidence(world)
    assert first is not None
    world.events.events.clear()
    world.events.drain(session)
    world.events.drain(session)
    second = _evidence(world)
    assert second is not None
    assert second.count == first.count == 1


def test_recover_applies_unmarked_outbox_once_without_replaying_history():
    world = build_app_world()
    original_drain = world.events.drain
    world.events.drain = lambda session=None: None
    session = _confirm_li_fuji(world)
    assert _evidence(world) is None
    pending_memory = world.outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER, event_types=(ORDER_CONFIRMED,))
    assert len(pending_memory) == 1
    world.events.events.clear()
    world.events.drain = original_drain
    world.events.recover()
    after = _evidence(world)
    assert after is not None
    assert after.count == 1
    assert any(item.event_type == ORDER_CONFIRMED for item in world.timeline.list(session.session_id))
    world.events.recover()
    again = _evidence(world)
    assert again is not None
    assert again.count == 1
    assert (
        world.outbox.list_pending(
            MEMORY_EXTRACTOR_CONSUMER,
            event_types=(ORDER_CONFIRMED,),
        )
        == []
    )
    assert world.outbox.list_pending(TIMELINE_CONSUMER) == []


def test_postgres_outbox_crash_before_drain_recover_exactly_once():
    url = postgres_url_or_skip()
    world1 = build_app_world(database_url=url, reset_schema=True)
    world1.events.drain = lambda session=None: None
    session = _confirm_li_fuji(world1)
    assert _evidence(world1) is None
    pending = world1.outbox.list_pending(MEMORY_EXTRACTOR_CONSUMER, event_types=(ORDER_CONFIRMED,))
    assert len(pending) == 1
    session_id = session.session_id
    if world1.engine is not None:
        world1.engine.dispose()

    world2 = build_app_world(database_url=url, reset_schema=False)
    restored = _evidence(world2)
    assert restored is not None
    assert restored.count == 1
    assert (
        world2.outbox.list_pending(
            MEMORY_EXTRACTOR_CONSUMER,
            event_types=(ORDER_CONFIRMED,),
        )
        == []
    )
    assert any(item.event_type == ORDER_CONFIRMED for item in world2.timeline.list(session_id))
    if world2.engine is not None:
        world2.engine.dispose()

    world3 = build_app_world(database_url=url, reset_schema=False)
    stable = _evidence(world3)
    assert stable is not None
    assert stable.count == 1
    if world3.engine is not None:
        world3.engine.dispose()
