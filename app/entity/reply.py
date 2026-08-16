from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.entity.issue import ReplyMode

ReplyScope = Literal["changed_only", "full"]
SourceKind = Literal["qty", "price", "sku", "customer", "stall", "uom"]
SourceOrigin = Literal["draft_line", "customer_ref", "issue_option", "verdict"]


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


class ReplyPlan(BaseModel):
    mode: ReplyMode
    reply_scope: ReplyScope = "full"
    confirmed: bool = False
    customer_label: str | None = None
    lines: list[ReplyLineFact] = Field(default_factory=list)
    question: ReplyQuestion | None = None
    source_refs: list[SourceRef] = Field(default_factory=list)
    must_say: list[str] = Field(default_factory=list)
