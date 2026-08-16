from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

PriceMemoryType = Literal["last_quote", "last_deal", "market_today", "customer_special"]
MemoryKind = Literal["product_alias", "price", "product_default"]
MemoryStatus = Literal["pending", "active", "retired"]


class ProductAliasMemory(BaseModel):
    alias: str
    node_id: UUID
    customer_id: UUID | None = None
    confidence: float = 1.0
    source: str = "utterance"
    updated_at: datetime | None = None
    status: MemoryStatus = "pending"
    last_confirmed_at: datetime | None = None


class PriceMemoryRecord(BaseModel):
    price_type: PriceMemoryType
    customer_id: UUID | None = None
    product_id: UUID
    unit_price: Decimal
    price_uom: str
    valid_until: datetime | None = None
    valid_from: datetime | None = None
    confidence: float = 1.0
    status: MemoryStatus = "pending"
    last_confirmed_at: datetime | None = None


class MemoryCandidate(BaseModel):
    kind: MemoryKind
    confidence: float = 0.0
    reason: str = ""
    alias: ProductAliasMemory | None = None
    price: PriceMemoryRecord | None = None
    source_act: str = ""
    source_event: str = ""
    customer_id: UUID | None = None
    node_id: UUID | None = None
    sku_id: UUID | None = None
    evidence_count: int = 0
    status: MemoryStatus = "pending"
    last_confirmed_at: datetime | None = None
