from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

FORBIDDEN_TIMELINE_KEYS = frozenset(
    {"user_text", "raw_text", "text", "utterance", "chat", "message"}
)


class TimelineEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    event_type: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)


def sanitize_timeline_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Timeline 只保留业务字段，丢弃用户原话类键。"""

    def clean(node: Any) -> Any:
        if isinstance(node, dict):
            out: dict[str, Any] = {}
            for key, value in node.items():
                if str(key).lower() in FORBIDDEN_TIMELINE_KEYS:
                    continue
                out[key] = clean(value)
            return out
        if isinstance(node, list):
            return [clean(item) for item in node]
        return node

    cleaned = clean(payload or {})
    return cleaned if isinstance(cleaned, dict) else {}
