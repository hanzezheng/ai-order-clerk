from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TurnIn(BaseModel):
    text: str
    source: Literal["voice", "text"] = "text"
    utterance_id: str
    seq: int = Field(ge=0)
    is_final: bool = True
    expect_more: bool = False


class SessionOut(BaseModel):
    session_id: UUID
    status: str
    draft: dict[str, Any]
    timeline: list[dict[str, Any]]
