"""categories and items

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_CATEGORIES = [
    "Produce",
    "Dairy",
    "Meat & Fish",
    "Bakery",
    "Pantry",
    "Frozen",
    "Drinks",
    "Cleaning",
    "Toiletries",
    "Household",
]


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    categories = op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *timestamps(),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=True),
        sa.Column("unit", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="needed", nullable=False),
        sa.Column("store", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        *timestamps(),
        sa.CheckConstraint("status IN ('needed', 'have', 'low')", name="ck_items_status"),
        sa.CheckConstraint("quantity >= 0", name="ck_items_quantity"),
    )
    op.create_index("uq_items_name_lower", "items", [sa.text("lower(name)")], unique=True)

    op.bulk_insert(
        categories,
        [{"id": uuid.uuid4(), "name": name, "sort_order": i} for i, name in enumerate(DEFAULT_CATEGORIES)],
    )


def downgrade() -> None:
    op.drop_index("uq_items_name_lower", table_name="items")
    op.drop_table("items")
    op.drop_table("categories")
