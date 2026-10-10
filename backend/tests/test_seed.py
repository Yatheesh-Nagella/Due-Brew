import pytest
from sqlalchemy import select

from due_brew import models
from due_brew.seed import parse_seed_users, seed_users

RAW = "alice@example.com:Alice:alice@example.com, bob@example.com:Bob:bob@example.com"


def test_parse_seed_users():
    assert parse_seed_users(RAW) == [
        {"tailscale_login": "alice@example.com", "display_name": "Alice", "email": "alice@example.com"},
        {"tailscale_login": "bob@example.com", "display_name": "Bob", "email": "bob@example.com"},
    ]


def test_parse_rejects_malformed_entries():
    with pytest.raises(ValueError):
        parse_seed_users("alice@example.com:Alice")


def test_seed_is_repeatable_and_keeps_user_edits(db):
    assert seed_users(db, RAW) == 2
    alice = db.scalar(select(models.User).where(models.User.display_name == "Alice"))
    alice.email = "changed-in-settings@example.com"
    db.commit()

    assert seed_users(db, RAW) == 0
    db.refresh(alice)
    assert alice.email == "changed-in-settings@example.com"
    assert alice.notify_mode == "individual"
