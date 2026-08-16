from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProductNodeRow(Base):
    __tablename__ = "product_nodes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    parent_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_nodes.id"))
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aliases: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    default_uom: Mapped[str] = mapped_column(String(32), nullable=False, default="件")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class CustomerRow(Base):
    __tablename__ = "customers"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stall_no: Mapped[str | None] = mapped_column(String(64))
    phones: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    aliases: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="trusted")
    confirm_count: Mapped[int] = mapped_column(nullable=False, default=0)


class CustomerProfileRow(Base):
    __tablename__ = "customer_profiles"

    customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("customers.id"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stall_no: Mapped[str | None] = mapped_column(String(64))
    phones: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    settlement_mode: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    price_tier: Mapped[str] = mapped_column(String(64), nullable=False, default="wholesale")
    product_defaults: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    preferred_uoms: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class ProductAliasRow(Base):
    __tablename__ = "product_aliases"

    alias: Mapped[str] = mapped_column(String(255), primary_key=True)
    node_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_nodes.id"), nullable=False)


class PriceMemoryRow(Base):
    __tablename__ = "price_memories"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    price_type: Mapped[str] = mapped_column(String(64), nullable=False)
    customer_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id"))
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("product_nodes.id"), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    price_uom: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvidenceRow(Base):
    __tablename__ = "evidence"

    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(String(64), primary_key=True)
    node_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    sku_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    count: Mapped[int] = mapped_column(nullable=False, default=0)
    positive_count: Mapped[int] = mapped_column(nullable=False, default=0)
    negative_count: Mapped[int] = mapped_column(nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionRow(Base):
    __tablename__ = "sales_sessions"

    session_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="drafting")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderRow(Base):
    __tablename__ = "orders"

    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    customer_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OrderLineRow(Base):
    __tablename__ = "order_lines"

    line_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("orders.order_id"), nullable=False)
    sku_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    uom: Mapped[str] = mapped_column(String(32), nullable=False)
    price_source: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    line_status: Mapped[str] = mapped_column(String(32), nullable=False)


class TimelineRow(Base):
    __tablename__ = "timeline_events"

    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class ProcessedEventRow(Base):
    __tablename__ = "processed_events"

    consumer: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)


class WorkbenchShiftRow(Base):
    __tablename__ = "workbench_shifts"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_session_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True))
    tasks: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)


class IntakeReceiptRow(Base):
    __tablename__ = "intake_receipts"
    __table_args__ = (UniqueConstraint("session_id", "utterance_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    utterance_id: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class IntakeSequenceRow(Base):
    __tablename__ = "intake_sequences"

    session_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    last_seq: Mapped[int] = mapped_column(nullable=False)
