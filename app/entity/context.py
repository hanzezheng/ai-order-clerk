from __future__ import annotations

from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.entity.memory import PriceMemoryType


class NoticePriority(str, Enum):
    """预留。Sprint 5A 不按此排序。"""

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class NoticeSeverity(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class ProfileDefaultFact(BaseModel):
    line_id: UUID
    sku_id: UUID
    sku_name: str


class PriceRiskFact(BaseModel):
    line_id: UUID | None = None
    sku_id: UUID
    price_type: PriceMemoryType
    unit_price: Decimal
    price_uom: str
    expired: bool = False


class BusinessContext(BaseModel):
    """只读投影：仅本单相关事实。禁止塞入全量 Profile/Memory。"""

    customer_id: UUID | None = None
    profile_defaults: list[ProfileDefaultFact] = Field(default_factory=list)
    price_facts: list[PriceRiskFact] = Field(default_factory=list)
