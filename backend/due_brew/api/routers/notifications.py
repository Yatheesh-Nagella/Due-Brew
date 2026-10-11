import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from due_brew import clock, models, schemas
from due_brew.config import get_settings
from due_brew.database import get_db
from due_brew.emails import compose, sender
from due_brew.identity import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])
log = logging.getLogger("uvicorn.error")

NL = models.NotificationLog


def notification_out(row: models.NotificationLog, items: int) -> schemas.NotificationOut:
    occ = row.occurrence
    return schemas.NotificationOut(
        id=row.id,
        kind=row.kind,
        status=row.status,
        user=row.user,
        to=row.user.email,
        subject=row.subject,
        bill_name=occ.bill.name if occ else None,
        due_date=occ.due_date if occ else None,
        items=items,
        attempts=row.attempts,
        last_error=row.last_error,
        created_at=row.created_at,
        sent_at=row.sent_at,
    )


@router.get("", response_model=list[schemas.NotificationOut])
def list_notifications(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """What the notifier sent, skipped or failed, newest first, for both housemates.
    Reminders inside a digest are folded into the digest's row."""
    rows = (
        db.scalars(select(NL).where(NL.digest_id.is_(None)).order_by(NL.created_at.desc()).limit(limit))
        .unique()
        .all()
    )
    digest_ids = [r.id for r in rows if r.kind == "digest"]
    counts = dict(
        db.execute(
            select(NL.digest_id, func.count(func.distinct(NL.occurrence_id)))
            .where(NL.digest_id.in_(digest_ids))
            .group_by(NL.digest_id)
        ).all()
    )
    return [notification_out(r, counts.get(r.id, 0) if r.kind == "digest" else 1) for r in rows]


@router.post("/test", response_model=schemas.NotificationOut)
def send_test_email(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """Email the current user right now, and log it like any other email."""
    email = compose.check_email(user.email, user.display_name, get_settings().app_base_url)
    now = clock.now()
    row = NL(id=uuid.uuid4(), kind="test", user_id=user.id, subject=email.subject, claimed_at=now, attempts=1)
    try:
        sender.get_sender().send(email)
    except Exception as exc:
        row.status, row.last_error = "failed", str(exc)[:500] or exc.__class__.__name__
        db.add(row)
        db.commit()
        log.warning("test email to %s failed: %s", user.email, row.last_error)
        raise HTTPException(
            status_code=502, detail=f"Couldn't send the test email: {row.last_error}"
        ) from None
    row.status, row.sent_at = "sent", now
    db.add(row)
    db.commit()
    db.refresh(row)
    return notification_out(row, 1)
