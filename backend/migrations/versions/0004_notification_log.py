"""notification log

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "notification_log",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "occurrence_id", UUID, sa.ForeignKey("bill_occurrences.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("rule_id", UUID, sa.ForeignKey("reminder_rules.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("digest_date", sa.Date(), nullable=True),
        sa.Column("digest_id", UUID, sa.ForeignKey("notification_log.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('reminder', 'overdue', 'digest', 'test')", name="ck_notification_log_kind"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')", name="ck_notification_log_status"
        ),
    )
    op.create_index(
        "uq_notification_log_reminder",
        "notification_log",
        ["occurrence_id", "rule_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'reminder'"),
    )
    op.create_index(
        "uq_notification_log_overdue",
        "notification_log",
        ["occurrence_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'overdue'"),
    )
    op.create_index(
        "uq_notification_log_digest",
        "notification_log",
        ["user_id", "digest_date"],
        unique=True,
        postgresql_where=sa.text("kind = 'digest'"),
    )
    op.create_index("ix_notification_log_created_at", "notification_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("notification_log")
