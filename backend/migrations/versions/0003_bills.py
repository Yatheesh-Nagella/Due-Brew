"""bills, assignees, occurrences and reminder rules

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "bills",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("recurrence", sa.String(), nullable=False),
        sa.Column("due_day", sa.Integer(), nullable=False),
        sa.Column("due_month", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *timestamps(),
        sa.CheckConstraint(
            "recurrence IN ('monthly', 'quarterly', 'yearly', 'once')", name="ck_bills_recurrence"
        ),
        sa.CheckConstraint("due_day BETWEEN 1 AND 31", name="ck_bills_due_day"),
        sa.CheckConstraint("due_month IS NULL OR due_month BETWEEN 1 AND 12", name="ck_bills_due_month"),
        sa.CheckConstraint("recurrence <> 'yearly' OR due_month IS NOT NULL", name="ck_bills_yearly_month"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_bills_amount"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_bills_end_date"),
    )
    op.create_table(
        "bill_assignees",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("bill_id", UUID, sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("bill_id", "user_id"),
    )
    op.create_table(
        "bill_occurrences",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("bill_id", UUID, sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_by", UUID, sa.ForeignKey("users.id"), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("bill_id", "due_date"),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_bill_occurrences_amount"),
    )
    op.create_table(
        "reminder_rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("bill_id", UUID, sa.ForeignKey("bills.id", ondelete="CASCADE"), nullable=False),
        sa.Column("days_before", sa.Integer(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("bill_id", "days_before"),
        sa.CheckConstraint("days_before BETWEEN 0 AND 30", name="ck_reminder_rules_days_before"),
    )


def downgrade() -> None:
    op.drop_table("reminder_rules")
    op.drop_table("bill_occurrences")
    op.drop_table("bill_assignees")
    op.drop_table("bills")
