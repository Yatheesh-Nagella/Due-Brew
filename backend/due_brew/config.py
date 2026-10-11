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
        seed_users=os.environ.get("SEED_USERS", ""),
    )
