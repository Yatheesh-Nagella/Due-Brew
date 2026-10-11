import os
from dataclasses import dataclass
from functools import lru_cache


def _bool(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    app_env: str
    tz: str
    dev_user_login: str | None
    now_override: str | None
    notifier_interval_seconds: int
    notifier_dry_run: bool
    occurrence_horizon_days: int
    catchup_hours: int
    stale_pending_minutes: int
    app_base_url: str
    smtp_host: str
    smtp_port: int
    smtp_username: str | None
    smtp_password: str | None
    smtp_starttls: bool
    email_from: str
    seed_users: str

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    # APP_ENV defaults to production so a missing variable fails closed:
    # no DEV_USER_LOGIN fallback, no NOW_OVERRIDE.
    return Settings(
        app_env=os.environ.get("APP_ENV", "production").strip().lower(),
        tz=os.environ.get("TZ", "America/Chicago"),
        dev_user_login=os.environ.get("DEV_USER_LOGIN") or None,
        now_override=os.environ.get("NOW_OVERRIDE") or None,
        notifier_interval_seconds=int(os.environ.get("NOTIFIER_INTERVAL_SECONDS", "300")),
        notifier_dry_run=_bool(os.environ.get("NOTIFIER_DRY_RUN")),
        occurrence_horizon_days=int(os.environ.get("OCCURRENCE_HORIZON_DAYS", "60")),
        catchup_hours=int(os.environ.get("CATCHUP_HOURS", "48")),
        stale_pending_minutes=int(os.environ.get("STALE_PENDING_MINUTES", "10")),
        app_base_url=os.environ.get("APP_BASE_URL", "http://localhost:8080/due-brew").rstrip("/"),
        smtp_host=os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_username=os.environ.get("SMTP_USERNAME") or None,
        smtp_password=os.environ.get("SMTP_PASSWORD") or None,
        # Gmail needs STARTTLS; a local Mailpit inbox doesn't offer it.
        smtp_starttls=_bool(os.environ.get("SMTP_STARTTLS", "true")),
        email_from=os.environ.get("EMAIL_FROM", "Due and Brew <due-brew@example.com>"),
        seed_users=os.environ.get("SEED_USERS", ""),
    )
