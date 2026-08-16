from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.entity.catalog import CustomerRef, ProductMention
from app.entity.issue import DecisionVerdict, Issue
from app.entity.order import DraftOrder, OrderLine
from app.entity.reply import ReplyPlan
from app.entity.speech import SpeechAct


class PendingCustomerCreate(BaseModel):
    mention: str


class SalesSession(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)
    session_type: str = "sales_order"
    status: str = "drafting"
    draft: DraftOrder = Field(default_factory=DraftOrder)
    focus_line_id: UUID | None = None
    pending_customer_candidates: list[CustomerRef] = Field(default_factory=list)
    pending_customer_create: PendingCustomerCreate | None = None
    deferred_issues: list[Issue] = Field(default_factory=list)
    turn_index: int = 0
    line_buffer: list[SpeechAct] = Field(default_factory=list)
    suppressed_default_node_ids: list[UUID] = Field(default_factory=list)
    product_mention_candidates: list[ProductMention] = Field(default_factory=list)


class TurnResult(BaseModel):
    reply_text: str
    session: SalesSession
    verdict: DecisionVerdict
    acts: list[SpeechAct] = Field(default_factory=list)
    commands_executed: list[str] = Field(default_factory=list)
    generator_name: str = "template"
    reply_fallback_reason: str | None = None
    reply_plan: ReplyPlan | None = None
