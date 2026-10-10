import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

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
