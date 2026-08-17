from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.entity.session import SalesSession

WorkbenchTaskStatus = Literal["drafting", "confirmed", "paused"]


class WorkbenchTaskRef(BaseModel):
    session_id: UUID
    order_id: UUID
    status: WorkbenchTaskStatus = "drafting"
    customer_id: UUID | None = None
    customer_label: str | None = None
    line_count: int = 0
    prices_incomplete: bool | None = None
    confirmed_at: datetime | None = None


class WorkbenchShift(BaseModel):
    business_date: date = Field(default_factory=lambda: datetime.now(UTC).date())
    current_session_id: UUID | None = None
    tasks: list[WorkbenchTaskRef] = Field(default_factory=list)


def _customer_label(customer) -> str | None:
    if customer is None:
        return None
    aliases = [item for item in (customer.aliases or []) if item]
    if aliases:
        return aliases[0]
    return customer.name


def project_task(session: SalesSession, *, previous: WorkbenchTaskRef | None = None) -> WorkbenchTaskRef:
    customer = session.draft.customer
    confirmed = session.draft.status == "confirmed" or session.status == "confirmed"
    status: WorkbenchTaskStatus = "confirmed" if confirmed else "drafting"
    confirmed_at = previous.confirmed_at if previous is not None else None
    if confirmed and confirmed_at is None:
        confirmed_at = datetime.now(UTC)
    prices_incomplete = None
    if confirmed:
        prices_incomplete = any(ln.price.source == "tbd" for ln in session.draft.lines)
    return WorkbenchTaskRef(
        session_id=session.session_id,
        order_id=session.draft.order_id,
        status=status,
        customer_id=customer.id if customer is not None else None,
        customer_label=_customer_label(customer),
        line_count=len(session.draft.lines),
        prices_incomplete=prices_incomplete,
        confirmed_at=confirmed_at,
    )
