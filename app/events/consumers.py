from __future__ import annotations

from app.entity.events import ORDER_CONFIRMED, PREFERENCE_ADJUSTED, DomainEvent
from app.entity.session import SalesSession
from app.events.dispatcher import EventConsumer
from app.memory.extractor import MemoryExtractor
from app.memory.policy import MemoryPolicy
from app.services.memory_service import MemoryService
from app.services.ports import MEMORY_EXTRACTOR_CONSUMER, TIMELINE_CONSUMER, ProcessedEventRepository
from app.session.timeline import SessionTimelineStore


class MemoryConsumer(EventConsumer):
    name = MEMORY_EXTRACTOR_CONSUMER
    event_types = (ORDER_CONFIRMED, PREFERENCE_ADJUSTED)

    def __init__(
        self,
        *,
        extractor: MemoryExtractor,
        policy: MemoryPolicy,
        memory: MemoryService,
        processed: ProcessedEventRepository,
    ) -> None:
        self._extractor = extractor
        self._policy = policy
        self._memory = memory
        self._processed = processed

    def consume(self, session: SalesSession | None, event: DomainEvent) -> None:
        if self._processed.has(self.name, event.event_id):
            return
        if session is None:
            return
        candidates = self._extractor.extract_from_events(session, [event])
        for candidate in candidates:
            decision = self._policy.decide(candidate)
            self._memory.apply(candidate, decision)
        self._processed.mark(self.name, event.event_id)


class TimelineConsumer(EventConsumer):
    name = TIMELINE_CONSUMER
    event_types = None

    def __init__(self, timeline: SessionTimelineStore) -> None:
        self._timeline = timeline

    def consume(self, session: SalesSession | None, event: DomainEvent) -> None:
        if session is None:
            return
        self._timeline.project_domain(session, [event])
