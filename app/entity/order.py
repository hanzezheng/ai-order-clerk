from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.entity.catalog import CustomerRef, ProductMention
from app.entity.price import PriceQuote

LineStatus = Literal["unresolved", "pending_clarify", "ready", "price_tbd", "confirmed"]


class Quantity(BaseModel):
    value: Decimal
    uom: str


class OrderLine(BaseModel):
    line_id: UUID = Field(default_factory=uuid4)
    mention: ProductMention
    product_sku_id: UUID | None = None
    matched_node_id: UUID | None = None
    qty: Quantity
    price: PriceQuote = Field(default_factory=PriceQuote)
    merge_op: str = "set"
    line_status: LineStatus = "unresolved"


class DraftOrder(BaseModel):
    order_id: UUID = Field(default_factory=uuid4)
    customer: CustomerRef | None = None
    status: str = "draft"
    lines: list[OrderLine] = Field(default_factory=list)
    remarks: str | None = None
    price_mode: str = "qty_first_price_optional"
