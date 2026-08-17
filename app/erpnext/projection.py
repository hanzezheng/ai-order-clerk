from __future__ import annotations

from typing import Any
from uuid import UUID


def attach_session_enterprise(world: Any, payload: dict) -> dict:
    """装配层侧栏。未确认不查 ERP。不写 draft.lines。"""

    draft = payload.get("draft") if isinstance(payload.get("draft"), dict) else {}
    if draft.get("status") != "confirmed":
        payload["enterprise"] = None
        return payload
    order_id = _as_uuid(draft.get("order_id"))
    if order_id is None:
        payload["enterprise"] = None
        return payload
    payload["enterprise"] = world.facts.posting_for(order_id).public()
    return payload


def attach_workbench_enterprise(world: Any, payload: dict) -> dict:
    for task in payload.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        if task.get("status") != "confirmed":
            task["posting"] = None
            continue
        order_id = _as_uuid(task.get("order_id"))
        if order_id is None:
            task["posting"] = None
            continue
        task["posting"] = world.facts.posting_for(order_id).posting
    payload["open_draft_count"] = _open_draft_count(world, payload)
    return payload


def _open_draft_count(world: Any, payload: dict) -> int | None:
    current = _as_uuid(payload.get("current_session_id"))
    if current is None:
        return None
    session = world.sessions.get(current)
    if session is None or session.draft.customer is None or session.draft.customer.id is None:
        return None
    return world.facts.open_draft_count(session.draft.customer.id)


def _as_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None
