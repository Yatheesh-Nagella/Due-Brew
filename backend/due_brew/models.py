import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from due_brew.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("notify_mode IN ('individual', 'digest')", name="ck_users_notify_mode"),
        CheckConstraint("digest_hour BETWEEN 0 AND 23", name="ck_users_digest_hour"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tailscale_login: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    notify_mode: Mapped[str] = mapped_column(String, nullable=False, server_default="individual")
    digest_hour: Mapped[int] = mapped_column(Integer, nullable=False, server_default="8")
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class NotifierHeartbeat(TimestampMixin, Base):
    """Single row (id = 1) the notifier bumps every tick; /api/health reports its age."""

    __tablename__ = "notifier_heartbeat"
    __table_args__ = (CheckConstraint("id = 1", name="ck_notifier_heartbeat_single_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    beat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


ITEM_STATUSES = ("needed", "have", "low")


class Item(TimestampMixin, Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("status IN ('needed', 'have', 'low')", name="ck_items_status"),
        CheckConstraint("quantity >= 0", name="ck_items_quantity"),
        # The duplicate guard: one row per name, ignoring case. Quick add relies
        # on this with INSERT ... ON CONFLICT so concurrent adds can't duplicate.
        Index("uq_items_name_lower", text("lower(name)"), unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="needed")
    store: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    category: Mapped[Category | None] = relationship(lazy="joined")
    added_by_user: Mapped[User] = relationship(foreign_keys=[added_by], lazy="joined")
    updated_by_user: Mapped[User] = relationship(foreign_keys=[updated_by], lazy="joined")
