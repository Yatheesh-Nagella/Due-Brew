"""users and notifier heartbeat

Revision ID: 0001
Revises:
Create Date: 2026-10-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tailscale_login", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("notify_mode", sa.String(), server_default="individual", nullable=False),
        sa.Column("digest_hour", sa.Integer(), server_default="8", nullable=False),
        sa.Column("email_enabled", sa.Boolean(), server_default="true", nullable=False),
        *timestamps(),
        sa.CheckConstraint("notify_mode IN ('individual', 'digest')", name="ck_users_notify_mode"),
        sa.CheckConstraint("digest_hour BETWEEN 0 AND 23", name="ck_users_digest_hour"),
        sa.UniqueConstraint("tailscale_login"),
    )
    op.create_table(
        "notifier_heartbeat",
        sa.Column("id", sa.Integer(), autoincrement=False, primary_key=True),
        sa.Column("beat_at", sa.DateTime(timezone=True), nullable=False),
        *timestamps(),
        sa.CheckConstraint("id = 1", name="ck_notifier_heartbeat_single_row"),
    )


def downgrade() -> None:
    op.drop_table("notifier_heartbeat")
    op.drop_table("users")
