from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

OntologyLevel = Literal["category", "variety", "cultivar", "sku"]


class ProductNode(BaseModel):
    id: UUID
    parent_id: UUID | None = None
    level: OntologyLevel
    name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    default_uom: str = "件"
    status: str = "active"


class ProductMention(BaseModel):
    raw: str
    matched_node: ProductNode | None = None
    resolved_sku: ProductNode | None = None
    resolve_level: OntologyLevel | None = None
    confidence: float = 0.0
    candidates: list[ProductNode] = Field(default_factory=list)
    filled_from: str | None = None
    status: str = "resolved"


class CustomerRef(BaseModel):
    id: UUID | None = None
    name: str
    stall_no: str | None = None
    phone_tail: str | None = None
    last_order_at: datetime | None = None
    aliases: list[str] = Field(default_factory=list)
    match_confidence: float = 0.0
    candidates: list[CustomerRef] = Field(default_factory=list)
    status: str = "trusted"
    needs_distinguisher: bool = False


class CustomerRecord(BaseModel):
    id: UUID
    legal_name: str
    display_name: str
    stall_no: str | None = None
    phones: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    status: str = "trusted"
    confirm_count: int = 0


class CustomerProfile(BaseModel):
    customer_id: UUID
    display_name: str
    stall_no: str | None = None
    phones: list[str] = Field(default_factory=list)
    settlement_mode: str = "unknown"
    price_tier: str = "wholesale"
    product_defaults: dict[str, UUID] = Field(default_factory=dict)
    preferred_uoms: dict[str, str] = Field(default_factory=dict)
