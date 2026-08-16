from __future__ import annotations

from uuid import UUID

from app.entity.catalog import CustomerProfile, CustomerRecord, ProductNode
from app.entity.order import DraftOrder
from app.entity.session import SalesSession


class CatalogRepository:
    def list_customers(self) -> list[CustomerRecord]:
        raise NotImplementedError

    def get_customer(self, customer_id: UUID) -> CustomerRecord | None:
        raise NotImplementedError

    def get_profile(self, customer_id: UUID) -> CustomerProfile | None:
        raise NotImplementedError

    def list_nodes(self) -> list[ProductNode]:
        raise NotImplementedError

    def get_node(self, node_id: UUID) -> ProductNode | None:
        raise NotImplementedError

    def put_customer(self, customer: CustomerRecord, profile: CustomerProfile) -> None:
        raise NotImplementedError


class SessionRepository:
    def get(self, session_id: UUID) -> SalesSession | None:
        raise NotImplementedError

    def save(self, session: SalesSession) -> None:
        raise NotImplementedError


class OrderRepository:
    def save_draft(self, draft: DraftOrder) -> None:
        raise NotImplementedError

    def get_draft(self, order_id: UUID) -> DraftOrder | None:
        raise NotImplementedError
