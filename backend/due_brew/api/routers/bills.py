import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from due_brew import bills, clock, models, schemas
from due_brew.database import get_db
from due_brew.identity import get_current_user

router = APIRouter(prefix="/api", tags=["bills"])

SCHEDULE_FIELDS = ("recurrence", "due_day", "due_month", "start_date", "end_date")


# --- shaping responses ---


def occurrence_out(occ: models.BillOccurrence, today: date) -> schemas.OccurrenceOut:
    days_until = (occ.due_date - today).days
    if occ.paid_at is not None:
        state = "paid"
    elif days_until < 0:
        state = "overdue"
    elif days_until == 0:
        state = "due_today"
    else:
        state = "upcoming"
    amount = occ.effective_amount
    return schemas.OccurrenceOut(
        id=occ.id,
        bill_id=occ.bill_id,
        bill_name=occ.bill.name,
        due_date=occ.due_date,
        amount=float(amount) if amount is not None else None,
        variable=occ.bill.amount is None,
        paid_at=occ.paid_at,
        paid_by_user=occ.paid_by_user,
        assignees=occ.bill.assignees,
        days_until=days_until,
        state=state,
    )


def bill_out(db: Session, bill: models.Bill, today: date) -> schemas.BillOut:
    next_occ = db.scalar(
        select(models.BillOccurrence)
        .where(models.BillOccurrence.bill_id == bill.id, models.BillOccurrence.paid_at.is_(None))
        .order_by(models.BillOccurrence.due_date)
        .limit(1)
    )
    paid_count = db.scalar(
        select(func.count())
        .select_from(models.BillOccurrence)
        .where(models.BillOccurrence.bill_id == bill.id, models.BillOccurrence.paid_at.is_not(None))
    )
    return schemas.BillOut(
        id=bill.id,
        name=bill.name,
        amount=float(bill.amount) if bill.amount is not None else None,
        recurrence=bill.recurrence,
        due_day=bill.due_day,
        due_month=bill.due_month,
        start_date=bill.start_date,
        end_date=bill.end_date,
        active=bill.active,
        notes=bill.notes,
        assignees=bill.assignees,
        reminder_days=[rule.days_before for rule in bill.reminder_rules],
        next_occurrence=occurrence_out(next_occ, today) if next_occ else None,
        paid_count=paid_count,
    )


# --- applying input ---


def _resolve_schedule(fields: dict, today: date) -> dict:
    """Fill defaults and apply the cross-field rules for each recurrence."""
    fields = dict(fields)
    recurrence = schemas.Recurrence(fields["recurrence"])
    fields["recurrence"] = recurrence.value
    if fields.get("start_date") is None:
        fields["start_date"] = today
    if recurrence is schemas.Recurrence.once:
        # A one-off bill is due on its start date.
        fields["due_day"] = fields["start_date"].day
        fields["due_month"] = None
    else:
        if fields.get("due_day") is None:
            raise HTTPException(status_code=422, detail="due_day is required")
        if recurrence is schemas.Recurrence.yearly:
            if fields.get("due_month") is None:
                raise HTTPException(status_code=422, detail="due_month is required for a yearly bill")
        else:
            fields["due_month"] = None
    if fields.get("end_date") is not None and fields["end_date"] < fields["start_date"]:
        raise HTTPException(status_code=422, detail="end_date cannot be before start_date")
    return fields


def _set_assignees(db: Session, bill: models.Bill, user_ids: list[uuid.UUID]) -> None:
    users = db.scalars(select(models.User).where(models.User.id.in_(user_ids))).all()
    if len(users) != len(set(user_ids)):
        raise HTTPException(status_code=422, detail="Unknown assignee")
    bill.assignees = list(users)


def _set_reminder_days(bill: models.Bill, days: list[int]) -> None:
    # Diff instead of replace-all, so (bill_id, days_before) never collides mid-flush.
    keep = set(days)
    bill.reminder_rules = [rule for rule in bill.reminder_rules if rule.days_before in keep]
    existing = {rule.days_before for rule in bill.reminder_rules}
    bill.reminder_rules.extend(models.ReminderRule(days_before=d) for d in days if d not in existing)


def _get_bill(db: Session, bill_id: uuid.UUID) -> models.Bill:
    bill = db.get(models.Bill, bill_id)
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill


def _get_occurrence(db: Session, occurrence_id: uuid.UUID) -> models.BillOccurrence:
    occ = db.get(models.BillOccurrence, occurrence_id)
    if not occ:
        raise HTTPException(status_code=404, detail="Occurrence not found")
    return occ


# --- bills ---


@router.get("/bills", response_model=list[schemas.BillOut])
def list_bills(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    today = clock.today()
    bills.sync_all(db, today)
    rows = db.scalars(select(models.Bill).order_by(models.Bill.active.desc(), func.lower(models.Bill.name)))
    return [bill_out(db, bill, today) for bill in rows.all()]


@router.post("/bills", response_model=schemas.BillOut, status_code=201)
def create_bill(
    body: schemas.BillCreate, db: Session = Depends(get_db), _: models.User = Depends(get_current_user)
):
    today = clock.today()
    fields = _resolve_schedule(body.model_dump(exclude={"assignee_ids", "reminder_days"}), today)
    bill = models.Bill(**fields)
    db.add(bill)
    _set_assignees(db, bill, body.assignee_ids)
    _set_reminder_days(bill, body.reminder_days)
    db.flush()
    bills.sync_occurrences(db, bill, today)
    db.commit()
    return bill_out(db, bill, today)


@router.get("/bills/upcoming", response_model=list[schemas.OccurrenceOut])
def upcoming(
    days: int = Query(30, ge=0, le=366),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Occurrences due from today through `days` ahead (paid or not), plus every
    overdue unpaid one, for active bills, soonest first."""
    today = clock.today()
    bills.sync_all(db, today)
    occ = models.BillOccurrence
    rows = db.scalars(
        select(occ)
        .join(models.Bill)
        .where(
            models.Bill.active,
            or_(
                and_(occ.paid_at.is_(None), occ.due_date < today),
                occ.due_date.between(today, today + timedelta(days=days)),
            ),
        )
        .order_by(occ.due_date, func.lower(models.Bill.name))
    )
    return [occurrence_out(o, today) for o in rows.unique().all()]


@router.get("/bills/{bill_id}", response_model=schemas.BillOut)
def get_bill(bill_id: uuid.UUID, db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    return bill_out(db, _get_bill(db, bill_id), clock.today())


@router.patch("/bills/{bill_id}", response_model=schemas.BillOut)
def update_bill(
    bill_id: uuid.UUID,
    body: schemas.BillUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    today = clock.today()
    bill = _get_bill(db, bill_id)
    changes = body.model_dump(exclude_unset=True)
    for required in ("name", "recurrence", "active"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} cannot be empty")
    assignee_ids = changes.pop("assignee_ids", None)
    reminder_days = changes.pop("reminder_days", None)

    current = {field: getattr(bill, field) for field in SCHEDULE_FIELDS}
    schedule = _resolve_schedule(
        {**current, **{k: v for k, v in changes.items() if k in SCHEDULE_FIELDS}}, today
    )
    for field, value in {**changes, **schedule}.items():
        setattr(bill, field, value)
    if assignee_ids is not None:
        _set_assignees(db, bill, assignee_ids)
    if reminder_days is not None:
        _set_reminder_days(bill, reminder_days)
    db.flush()
    bills.sync_occurrences(db, bill, today)
    db.commit()
    db.refresh(bill)
    return bill_out(db, bill, today)


@router.delete("/bills/{bill_id}", status_code=204)
def delete_bill(
    bill_id: uuid.UUID,
    confirm: bool = False,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    bill = _get_bill(db, bill_id)
    paid = db.scalar(
        select(func.count())
        .select_from(models.BillOccurrence)
        .where(models.BillOccurrence.bill_id == bill.id, models.BillOccurrence.paid_at.is_not(None))
    )
    if paid and not confirm:
        raise HTTPException(
            status_code=409,
            detail=f"{bill.name} has {paid} paid payment(s) on record. Deactivate it to keep the "
            "history, or delete with confirm=true.",
        )
    db.delete(bill)
    db.commit()


# --- occurrences ---


@router.post("/occurrences/{occurrence_id}/paid", response_model=schemas.OccurrenceOut)
def mark_paid(
    occurrence_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    occ = _get_occurrence(db, occurrence_id)
    if occ.paid_at is None:  # paying twice keeps the first payment's record
        occ.paid_at = clock.now()
        occ.paid_by = user.id
        db.commit()
        db.refresh(occ)
    return occurrence_out(occ, clock.today())


@router.delete("/occurrences/{occurrence_id}/paid", response_model=schemas.OccurrenceOut)
def undo_paid(
    occurrence_id: uuid.UUID, db: Session = Depends(get_db), _: models.User = Depends(get_current_user)
):
    occ = _get_occurrence(db, occurrence_id)
    occ.paid_at = None
    occ.paid_by = None
    db.commit()
    db.refresh(occ)
    return occurrence_out(occ, clock.today())


@router.patch("/occurrences/{occurrence_id}", response_model=schemas.OccurrenceOut)
def set_occurrence_amount(
    occurrence_id: uuid.UUID,
    body: schemas.OccurrenceUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    """Set this occurrence's amount (a variable bill's actual amount, or a one-off
    override); null goes back to the bill's amount."""
    occ = _get_occurrence(db, occurrence_id)
    occ.amount = body.amount
    db.commit()
    db.refresh(occ)
    return occurrence_out(occ, clock.today())
