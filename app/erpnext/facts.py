from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

PostingStatus = Literal["pending", "posted", "unavailable"]


@dataclass(frozen=True)
class OrderPostingFact:
    """领域投递事实。禁止携带 item_code / doctype / warehouse / ERP name。"""

    runtime_order_id: UUID
    posting: PostingStatus
    prices_incomplete: bool | None = None
    line_count: int | None = None

    def public(self) -> dict:
        return {
            "posting": self.posting,
            "prices_incomplete": self.prices_incomplete,
            "line_count": self.line_count,
        }


class EnterpriseFactPort(Protocol):
    """装配层领域查询。签名只有 Runtime UUID。"""

    def posting_for(self, runtime_order_id: UUID) -> OrderPostingFact: ...

    def open_draft_count(self, runtime_customer_id: UUID) -> int | None: ...
