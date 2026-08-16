from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.entity.context import NoticePriority, NoticeSeverity
from app.entity.issue import ReplyMode

ReplyScope = Literal["changed_only", "full"]
SourceKind = Literal["qty", "price", "sku", "customer", "stall", "uom"]
SourceOrigin = Literal["draft_line", "customer_ref", "issue_option", "verdict", "memory_fact"]


class SourceRef(BaseModel):
    kind: SourceKind
    text: str
    origin: SourceOrigin
    subject_id: UUID | None = None


class ReplyLineFact(BaseModel):
    line_id: UUID | None = None
    label: str
    qty_text: str
    uom: str = ""
    price_text: str | None = None
    price_uom: str | None = None
    price_tbd: bool = False
    from_profile: bool = False
    sku_text: str | None = None


class ReplyQuestion(BaseModel):
    code: str
    option_labels: list[str] = Field(default_factory=list)


class ReplyNotice(BaseModel):
    code: str
    severity: NoticeSeverity = NoticeSeverity.NORMAL
    source_refs: list[SourceRef] = Field(default_factory=list)
    priority: NoticePriority = NoticePriority.NORMAL


class ReplyPlan(BaseModel):
    mode: ReplyMode
    reply_scope: ReplyScope = "full"
    confirmed: bool = False
    customer_label: str | None = None
    lines: list[ReplyLineFact] = Field(default_factory=list)
    question: ReplyQuestion | None = None
    notices: list[ReplyNotice] = Field(default_factory=list)
    source_refs: list[SourceRef] = Field(default_factory=list)
    must_say: list[str] = Field(default_factory=list)
