"""Create the housemates from SEED_USERS (login:Name:email,login:Name:email).

Runs on every API start. Existing users are left untouched, so edits made in
Settings (email, notify mode) are never overwritten by the seed.

    python -m due_brew.seed
"""

import logging

from sqlalchemy.dialects.postgresql import insert

from due_brew import models
from due_brew.config import get_settings
from due_brew.database import SessionLocal

log = logging.getLogger(__name__)


def parse_seed_users(raw: str) -> list[dict[str, str]]:
    users = []
    for entry in filter(None, (part.strip() for part in raw.split(","))):
        fields = [field.strip() for field in entry.split(":")]
        if len(fields) != 3 or not all(fields):
            raise ValueError(f"SEED_USERS entry must be login:Name:email, got {entry!r}")
        login, name, email = fields
        users.append({"tailscale_login": login, "display_name": name, "email": email})
    return users


def seed_users(db, raw: str) -> int:
    users = parse_seed_users(raw)
    if not users:
        return 0
    stmt = (
        insert(models.User)
        .values(users)
        .on_conflict_do_nothing(index_elements=["tailscale_login"])
        .returning(models.User.id)
    )
    created = len(db.execute(stmt).all())
    db.commit()
    return created


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [seed] %(message)s")
    with SessionLocal() as db:
        created = seed_users(db, get_settings().seed_users)
    log.info("seeded %d new user(s)", created)


if __name__ == "__main__":
    main()
