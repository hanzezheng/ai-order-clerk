from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from app.entity.issue import Issue
from app.entity.order import OrderLine
from app.entity.session import SalesSession, TurnResult
from app.entity.timeline import TimelineEvent
from app.services.ports import SessionRepository
from app.session.runner import SalesSessionRunner
from app.session.timeline import SessionTimelineStore
from app.entity.events import RecordingEventPublisher


class TurnCommand(BaseModel):
    text: str
    source: Literal["voice", "text"] = "text"
    utterance_id: str
    seq: int
    is_final: bool = True
    expect_more: bool = False


class IntakeError(Exception):
    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


class TurnIntake:
    """HTTP 适配层：幂等、保序、丢弃 partial，再交给现有 Runner。"""

    def __init__(
        self,
        *,
        runner: SalesSessionRunner,
        sessions: SessionRepository,
        events: RecordingEventPublisher,
        timeline: SessionTimelineStore,
    ) -> None:
        self._runner = runner
        self._sessions = sessions
        self._events = events
        self._timeline = timeline
        self._receipts: dict[tuple[UUID, str], dict[str, Any]] = {}
        self._last_seq: dict[UUID, int] = {}

    def create_session(self) -> SalesSession:
        session = SalesSession()
        self._sessions.save(session)
        stored = self._sessions.get(session.session_id)
        assert stored is not None
        return stored

    def get_session(self, session_id: UUID) -> SalesSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise IntakeError(404, "session_not_found")
        return session

    def snapshot(self, session: SalesSession) -> dict[str, Any]:
        return {
            "session_id": str(session.session_id),
            "status": session.status,
            "draft": project_draft(session),
            "timeline": [project_timeline_event(item) for item in self._timeline.list(session.session_id)],
        }

    def handle(self, session_id: UUID, command: TurnCommand) -> dict[str, Any]:
        session = self.get_session(session_id)
        cached = self._receipts.get((session_id, command.utterance_id))
        if cached is not None:
            return cached
        if not command.is_final:
            return self._ignored_payload(session)
        self._assert_seq(session_id, command.seq)
        result = self._runner.handle(session, command.text, expect_more=command.expect_more)
        live = result.session
        self._timeline.project_domain(live, self._events.events)
        self._timeline.project_session_blocks(live, result.verdict.issues)
        payload = self._accepted_payload(live, result)
        self._receipts[(session_id, command.utterance_id)] = payload
        self._last_seq[session_id] = command.seq
        return payload

    def _assert_seq(self, session_id: UUID, seq: int) -> None:
        last = self._last_seq.get(session_id)
        if last is None:
            return
        if seq != last + 1:
            raise IntakeError(409, "seq_out_of_order")

    def _ignored_payload(self, session: SalesSession) -> dict[str, Any]:
        return {
            "session_id": str(session.session_id),
            "ignored": True,
            "reply_text": "",
            "reply_mode": "ack",
            "commands_executed": [],
            "verdict": {"confirm_ok": False, "reply_mode": "ack", "issues": []},
            "draft": project_draft(session),
            "timeline": [project_timeline_event(item) for item in self._timeline.list(session.session_id)],
        }

    def _accepted_payload(self, session: SalesSession, result: TurnResult) -> dict[str, Any]:
        return {
            "session_id": str(session.session_id),
            "ignored": False,
            "reply_text": result.reply_text,
            "reply_mode": result.verdict.reply_mode,
            "commands_executed": list(result.commands_executed),
            "verdict": {
                "confirm_ok": result.verdict.confirm_ok,
                "reply_mode": result.verdict.reply_mode,
                "issues": [project_issue(issue) for issue in result.verdict.issues],
            },
            "draft": project_draft(session),
            "timeline": [project_timeline_event(item) for item in self._timeline.list(session.session_id)],
        }


def project_issue(issue: Issue) -> dict[str, Any]:
    return {
        "code": issue.code,
        "block_level": issue.block_level,
        "options": issue.options,
    }


def project_timeline_event(event: TimelineEvent) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "occurred_at": event.occurred_at.isoformat(),
        "payload": event.payload,
    }


def project_draft(session: SalesSession) -> dict[str, Any]:
    customer = session.draft.customer
    return {
        "order_id": str(session.draft.order_id),
        "status": session.draft.status,
        "customer": None
        if customer is None
        else {
            "id": str(customer.id) if customer.id else None,
            "name": customer.name,
            "stall_no": customer.stall_no,
        },
        "lines": [project_line(line) for line in session.draft.lines],
    }


def project_line(line: OrderLine) -> dict[str, Any]:
    node = line.mention.resolved_sku or line.mention.matched_node
    return {
        "line_id": str(line.line_id),
        "label": node.name if node else "未识别",
        "qty": str(line.qty.value),
        "uom": line.qty.uom,
        "price_status": line.price.source,
        "unit_price": str(line.price.unit_price) if line.price.unit_price is not None else None,
        "line_status": line.line_status,
    }
