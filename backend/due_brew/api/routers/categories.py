import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from due_brew import models, schemas
from due_brew.database import get_db
from due_brew.identity import get_current_user

router = APIRouter(prefix="/api/categories", tags=["categories"], dependencies=[Depends(get_current_user)])


def _get(db: Session, category_id: uuid.UUID) -> models.Category:
    category = db.get(models.Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def _commit_unique_name(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A category with this name already exists") from None


@router.get("", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.scalars(
        select(models.Category).order_by(models.Category.sort_order, models.Category.name)
    ).all()


@router.post("", response_model=schemas.CategoryOut, status_code=201)
def create_category(body: schemas.CategoryCreate, db: Session = Depends(get_db)):
    sort_order = body.sort_order
    if sort_order is None:
        sort_order = (db.scalar(select(func.max(models.Category.sort_order))) or 0) + 1
    category = models.Category(name=body.name, sort_order=sort_order)
    db.add(category)
    _commit_unique_name(db)
    db.refresh(category)
    return category


@router.patch("/{category_id}", response_model=schemas.CategoryOut)
def update_category(category_id: uuid.UUID, body: schemas.CategoryUpdate, db: Session = Depends(get_db)):
    category = _get(db, category_id)
    if body.name is not None:
        category.name = body.name
    if body.sort_order is not None:
        category.sort_order = body.sort_order
    _commit_unique_name(db)
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, db: Session = Depends(get_db)):
    # Items in it become uncategorized (ON DELETE SET NULL), they aren't deleted.
    db.delete(_get(db, category_id))
    db.commit()
