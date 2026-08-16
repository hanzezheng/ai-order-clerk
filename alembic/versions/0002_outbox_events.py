"""add outbox_events

Revision ID: 0002_outbox_events
Revises: 0001_init_persistence
Create Date: 2026-08-16

"""

from collections.abc import Sequence

from alembic import op

from app.database.postgres.models import OutboxRow

revision: str = "0002_outbox_events"
down_revision: str | None = "0001_init_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    OutboxRow.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    OutboxRow.__table__.drop(bind=op.get_bind(), checkfirst=True)
