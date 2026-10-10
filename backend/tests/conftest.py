from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from due_brew.database import SessionLocal, engine

# The suite truncates every table between tests, so refuse to run against
# anything that isn't clearly a throwaway test database.
if not (engine.url.database or "").endswith("_test"):
    raise RuntimeError(
        f"Refusing to run tests against database {engine.url.database!r}; "
        "point DATABASE_URL at a database whose name ends in '_test'."
    )

from due_brew import models  # noqa: E402
from due_brew.api.main import app  # noqa: E402
from due_brew.config import get_settings  # noqa: E402
from due_brew.identity import get_current_user  # noqa: E402


@pytest.fixture(scope="session")
def alembic_cfg():
    return Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))


@pytest.fixture(scope="session", autouse=True)
def migrated_schema(alembic_cfg):
    # Build the schema the same way production does, so migrations are tested too.
    command.upgrade(alembic_cfg, "head")


@pytest.fixture(autouse=True)
def clean_db():
    yield
    app.dependency_overrides.clear()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE users, notifier_heartbeat CASCADE"))


@pytest.fixture
def env(monkeypatch):
    """Set environment variables for one test: env(APP_ENV="production", ...)."""

    def _set(**values):
        for key, value in values.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        get_settings.cache_clear()

    # Start every test from a known, development-like baseline.
    _set(APP_ENV="development", DEV_USER_LOGIN=None, NOW_OVERRIDE=None, TZ="America/Chicago")
    yield _set
    get_settings.cache_clear()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def make_user(db):
    counter = iter(range(1, 1000))

    def _make(**overrides):
        n = next(counter)
        fields = {
            "tailscale_login": f"housemate{n}@example.com",
            "display_name": f"Housemate {n}",
            "email": f"housemate{n}@example.com",
            **overrides,
        }
        user = models.User(**fields)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def client(env):
    return TestClient(app)


@pytest.fixture
def as_user(client):
    """Act as a given user by overriding get_current_user, not by faking headers."""

    def _as(user):
        app.dependency_overrides[get_current_user] = lambda: user
        return client

    return _as
