import uuid
from enum import Enum

from pydantic import BaseModel, ConfigDict


class NotifyMode(str, Enum):
    individual = "individual"
    digest = "digest"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tailscale_login: str
    display_name: str
    email: str
    notify_mode: NotifyMode
    digest_hour: int
    email_enabled: bool


class HealthOut(BaseModel):
    status: str
    db: str
    notifier_heartbeat_age_seconds: float | None
