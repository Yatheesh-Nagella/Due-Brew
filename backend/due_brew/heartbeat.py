from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from due_brew import clock, models


def beat(db: Session) -> None:
    at = clock.now()
    stmt = insert(models.NotifierHeartbeat).values(id=1, beat_at=at)
    db.execute(stmt.on_conflict_do_update(index_elements=["id"], set_={"beat_at": at}))
    db.commit()


def last_beat(db: Session) -> datetime | None:
    return db.scalar(select(models.NotifierHeartbeat.beat_at).where(models.NotifierHeartbeat.id == 1))
