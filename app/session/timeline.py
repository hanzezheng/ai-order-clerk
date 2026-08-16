from __future__ import annotations

from uuid import UUID, uuid4

from app.entity.events import DomainEvent
from app.entity.issue import Issue
from app.entity.session import SalesSession
from app.entity.timeline import TimelineEvent, sanitize_timeline_payload


class SessionTimelineStore:
    """按会话追加业务事件。禁止当作聊天记录。"""

    def __init__(self) -> None:
        self._items: dict[UUID, list[TimelineEvent]] = {}
        self._seen_domain: set[UUID] = set()

    def list(self, session_id: UUID) -> list[TimelineEvent]:
        return [item.model_copy(deep=True) for item in self._items.get(session_id, [])]

    def append(self, event: TimelineEvent) -> TimelineEvent:
        event.payload = sanitize_timeline_payload(event.payload)
        bucket = self._items.setdefault(event.session_id, [])
        stored = event.model_copy(deep=True)
        bucket.append(stored)
        return stored

    def project_domain(self, session: SalesSession, events: list[DomainEvent]) -> None:
        order_id = session.draft.order_id
        for event in events:
            if event.event_id in self._seen_domain:
                continue
            payload = event.payload or {}
            belongs = str(payload.get("session_id", "")) == str(session.session_id)
            belongs = belongs or event.aggregate_id == order_id
            if not belongs:
                continue
            self._seen_domain.add(event.event_id)
            self.append(
                TimelineEvent(
                    event_id=event.event_id,
                    session_id=session.session_id,
                    event_type=event.event_type,
                    occurred_at=event.occurred_at,
                    payload=dict(payload),
                )
            )

    def project_session_blocks(self, session: SalesSession, issues: list[Issue]) -> None:
        for issue in issues:
            if issue.block_level != "session_block":
                continue
            payload: dict[str, object] = {"code": issue.code}
            names = [opt.get("name") for opt in issue.options if isinstance(opt, dict) and opt.get("name")]
            if names:
                payload["candidates"] = names
            self.append(
                TimelineEvent(
                    event_id=uuid4(),
                    session_id=session.session_id,
                    event_type=issue.code,
                    payload=payload,
                )
            )
