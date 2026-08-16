from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.database.memory import default_customers, default_nodes, default_profiles
from app.database.postgres.models import CustomerProfileRow, CustomerRow, ProductNodeRow


def seed_catalog(engine: Engine) -> None:
    """稳定 UUID upsert。客户/档案已存在则不覆盖，避免冲掉学习结果。"""
    with Session(engine) as db:
        for node in default_nodes():
            stmt = (
                insert(ProductNodeRow)
                .values(
                    id=node.id,
                    parent_id=node.parent_id,
                    level=node.level,
                    name=node.name,
                    aliases=list(node.aliases),
                    attributes=dict(node.attributes),
                    default_uom=node.default_uom,
                    status=node.status,
                )
                .on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "parent_id": node.parent_id,
                        "level": node.level,
                        "name": node.name,
                        "aliases": list(node.aliases),
                        "attributes": dict(node.attributes),
                        "default_uom": node.default_uom,
                        "status": node.status,
                    },
                )
            )
            db.execute(stmt)
        for customer in default_customers():
            stmt = (
                insert(CustomerRow)
                .values(
                    id=customer.id,
                    legal_name=customer.legal_name,
                    display_name=customer.display_name,
                    stall_no=customer.stall_no,
                    phones=list(customer.phones),
                    aliases=list(customer.aliases),
                    status=customer.status,
                    confirm_count=customer.confirm_count,
                )
                .on_conflict_do_nothing(index_elements=["id"])
            )
            db.execute(stmt)
        for profile in default_profiles().values():
            defaults = {str(k): str(v) for k, v in profile.product_defaults.items()}
            stmt = (
                insert(CustomerProfileRow)
                .values(
                    customer_id=profile.customer_id,
                    display_name=profile.display_name,
                    stall_no=profile.stall_no,
                    phones=list(profile.phones),
                    settlement_mode=profile.settlement_mode,
                    price_tier=profile.price_tier,
                    product_defaults=defaults,
                    preferred_uoms=dict(profile.preferred_uoms),
                )
                .on_conflict_do_nothing(index_elements=["customer_id"])
            )
            db.execute(stmt)
        db.commit()
