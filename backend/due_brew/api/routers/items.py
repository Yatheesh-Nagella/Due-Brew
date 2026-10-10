import uuid
from itertools import groupby

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from due_brew import models, schemas
from due_brew.database import get_db
from due_brew.identity import get_current_user

router = APIRouter(prefix="/api", tags=["items"])

# Needed before Low on the grocery list.
STATUS_RANK = {"needed": 0, "low": 1, "have": 2}


def _get(db: Session, item_id: uuid.UUID) -> models.Item:
    item = db.get(models.Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def _check_category(db: Session, category_id: uuid.UUID | None) -> None:
    if category_id is not None and db.get(models.Category, category_id) is None:
        raise HTTPException(status_code=422, detail="Category not found")


def _set_status(db: Session, item: models.Item, status: str, user: models.User) -> models.Item:
    item.status = status
    item.updated_by = user.id
    db.commit()
    db.refresh(item)
    return item


def _sort_key(item: models.Item):
    category = item.category
    return (
        category is None,
        category.sort_order if category else 0,
        category.name if category else "",
        item.name.lower(),
    )


@router.get("/items", response_model=list[schemas.ItemOut])
def list_items(
    status: schemas.ItemStatus | None = None,
    category_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    query = select(models.Item)
    if status is not None:
        query = query.where(models.Item.status == status.value)
    if category_id is not None:
        query = query.where(models.Item.category_id == category_id)
    return sorted(db.scalars(query).unique().all(), key=_sort_key)


@router.post("/items", response_model=schemas.ItemOut, status_code=201)
def create_item(
    body: schemas.ItemCreate,
    response: Response,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Create an item, or, if one with the same name (ignoring case) exists,
    put that one back on the list as Need instead (200 rather than 201)."""
    _check_category(db, body.category_id)
    values = body.model_dump()
    values["status"] = body.status.value
    stmt = (
        insert(models.Item)
        .values(id=uuid.uuid4(), added_by=user.id, updated_by=user.id, **values)
        .on_conflict_do_update(
            index_elements=[func.lower(models.Item.name)],
            set_={"status": "needed", "updated_by": user.id, "updated_at": func.now()},
        )
        # xmax = 0 only for a freshly inserted row, so this tells insert from update.
        .returning(models.Item.id, literal_column("xmax = 0").label("inserted"))
    )
    item_id, inserted = db.execute(stmt).one()
    db.commit()
    if not inserted:
        response.status_code = 200
    return _get(db, item_id)


@router.patch("/items/{item_id}", response_model=schemas.ItemOut)
def update_item(
    item_id: uuid.UUID,
    body: schemas.ItemUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    item = _get(db, item_id)
    changes = body.model_dump(exclude_unset=True)
    for required in ("name", "status"):
        if required in changes and changes[required] is None:
            raise HTTPException(status_code=422, detail=f"{required} cannot be empty")
    if "category_id" in changes:
        _check_category(db, changes["category_id"])
    for field, value in changes.items():
        setattr(item, field, value.value if isinstance(value, schemas.ItemStatus) else value)
    item.updated_by = user.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An item with this name already exists") from None
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=204)
def delete_item(
    item_id: uuid.UUID, db: Session = Depends(get_db), _: models.User = Depends(get_current_user)
):
    db.delete(_get(db, item_id))
    db.commit()


@router.post("/items/{item_id}/bought", response_model=schemas.ItemOut)
def mark_bought(
    item_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return _set_status(db, _get(db, item_id), "have", user)


@router.post("/items/{item_id}/add-to-list", response_model=schemas.ItemOut)
def add_to_list(
    item_id: uuid.UUID, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    return _set_status(db, _get(db, item_id), "needed", user)


@router.get("/grocery-list", response_model=schemas.GroceryList)
def grocery_list(
    group_by: str = Query("category", pattern="^(category|store)$"),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    items = db.scalars(select(models.Item).where(models.Item.status.in_(["needed", "low"]))).unique().all()

    if group_by == "store":

        def group_of(item):
            store = item.store
            return (store is None, (store or "").lower()), store, store or "Any store"
    else:

        def group_of(item):
            c = item.category
            return (
                (c is None, c.sort_order if c else 0, c.name if c else ""),
                str(c.id) if c else None,
                c.name if c else "Uncategorized",
            )

    ordered = sorted(items, key=lambda i: (group_of(i)[0], STATUS_RANK[i.status], i.name.lower()))
    groups = []
    # Group on the sort key alone, so "Costco" and "costco" land together; the
    # group takes its key and label from its first item.
    for _, members in groupby(ordered, key=lambda i: group_of(i)[0]):
        members = list(members)
        _, key, label = group_of(members[0])
        groups.append(schemas.GroceryGroup(key=key, label=label, items=members))
    return schemas.GroceryList(
        need_count=sum(i.status == "needed" for i in items),
        low_count=sum(i.status == "low" for i in items),
        groups=groups,
    )
