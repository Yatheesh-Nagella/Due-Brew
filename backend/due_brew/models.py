import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
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


class Bill(TimestampMixin, Base):
    __tablename__ = "bills"
    __table_args__ = (
        CheckConstraint(
            "recurrence IN ('monthly', 'quarterly', 'yearly', 'once')", name="ck_bills_recurrence"
        ),
        CheckConstraint("due_day BETWEEN 1 AND 31", name="ck_bills_due_day"),
        CheckConstraint("due_month IS NULL OR due_month BETWEEN 1 AND 12", name="ck_bills_due_month"),
        CheckConstraint("recurrence <> 'yearly' OR due_month IS NOT NULL", name="ck_bills_yearly_month"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_bills_amount"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_bills_end_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # NULL = a variable bill; the amount is entered on each occurrence.
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    recurrence: Mapped[str] = mapped_column(String, nullable=False)
    due_day: Mapped[int] = mapped_column(Integer, nullable=False)
    due_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    assignees: Mapped[list[User]] = relationship(
        secondary="bill_assignees", order_by="User.display_name", lazy="selectin"
    )
    reminder_rules: Mapped[list["ReminderRule"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
        order_by="ReminderRule.days_before.desc()",
        lazy="selectin",
    )
    occurrences: Mapped[list["BillOccurrence"]] = relationship(
        back_populates="bill", cascade="all, delete-orphan", passive_deletes=True
    )


class BillAssignee(TimestampMixin, Base):
    __tablename__ = "bill_assignees"
    __table_args__ = (UniqueConstraint("bill_id", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )


class BillOccurrence(TimestampMixin, Base):
    __tablename__ = "bill_occurrences"
    __table_args__ = (
        UniqueConstraint("bill_id", "due_date"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_bill_occurrences_amount"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    # NULL = use the bill's amount; set for variable bills or a one-off override.
    amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    bill: Mapped[Bill] = relationship(back_populates="occurrences", lazy="joined")
    paid_by_user: Mapped[User | None] = relationship(lazy="joined")

    @property
    def effective_amount(self) -> Decimal | None:
        return self.amount if self.amount is not None else self.bill.amount


class ReminderRule(TimestampMixin, Base):
    __tablename__ = "reminder_rules"
    __table_args__ = (
        UniqueConstraint("bill_id", "days_before"),
        CheckConstraint("days_before BETWEEN 0 AND 30", name="ck_reminder_rules_days_before"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bills.id", ondelete="CASCADE"), nullable=False
    )
    days_before: Mapped[int] = mapped_column(Integer, nullable=False)

    bill: Mapped[Bill] = relationship(back_populates="reminder_rules")


NOTIFICATION_KINDS = ("reminder", "overdue", "digest", "test")
NOTIFICATION_STATUSES = ("pending", "sent", "failed", "skipped")


class NotificationLog(TimestampMixin, Base):
    """One row per email the notifier owes someone. Inserting the row *claims*
    the send; the partial unique indexes below are what make sending idempotent:
    a second tick's INSERT ... ON CONFLICT DO NOTHING simply finds it taken."""

    __tablename__ = "notification_log"
    __table_args__ = (
        CheckConstraint("kind IN ('reminder', 'overdue', 'digest', 'test')", name="ck_notification_log_kind"),
        CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')", name="ck_notification_log_status"
        ),
        Index(
            "uq_notification_log_reminder",
            "occurrence_id",
            "rule_id",
            "user_id",
            unique=True,
            postgresql_where=text("kind = 'reminder'"),
        ),
        Index(
            "uq_notification_log_overdue",
            "occurrence_id",
            "user_id",
            unique=True,
            postgresql_where=text("kind = 'overdue'"),
        ),
        Index(
            "uq_notification_log_digest",
            "user_id",
            "digest_date",
            unique=True,
            postgresql_where=text("kind = 'digest'"),
        ),
        Index("ix_notification_log_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    occurrence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bill_occurrences.id", ondelete="CASCADE"), nullable=True
    )
    # SET NULL keeps the history when a reminder rule is removed from a bill.
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reminder_rules.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    digest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Reminder/overdue rows sent as part of a digest point at that digest's row.
    digest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("notification_log.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(lazy="joined")
    occurrence: Mapped[BillOccurrence | None] = relationship(lazy="joined")
