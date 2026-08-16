from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

BlockLevel = Literal["session_block", "line_hold", "notice"]
AskWhen = Literal["now", "idle", "confirm"]
ReplyMode = Literal["ack", "recap", "ask"]


class Issue(BaseModel):
    code: str
    block_level: BlockLevel
    subject_line_id: UUID | None = None
    options: list[dict[str, Any]] = Field(default_factory=list)
    ask_when: AskWhen = "now"
    message: str = ""


class DecisionVerdict(BaseModel):
    allow_execute: bool = True
    issues: list[Issue] = Field(default_factory=list)
    confirm_ok: bool = False
    reasons: list[str] = Field(default_factory=list)
    reply_mode: ReplyMode = "recap"
