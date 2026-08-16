from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class IntakeReceipt(BaseModel):
    session_id: UUID
    utterance_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
