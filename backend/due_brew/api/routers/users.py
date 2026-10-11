from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from due_brew import models, schemas
from due_brew.database import get_db
from due_brew.identity import get_current_user

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
def get_me(user: models.User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    body: schemas.MeUpdate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    me = db.merge(user)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be empty")
        setattr(me, field, value.value if isinstance(value, schemas.NotifyMode) else value)
    db.commit()
    db.refresh(me)
    return me


@router.get("/users", response_model=list[schemas.UserBrief])
def list_users(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    return db.scalars(select(models.User).order_by(models.User.display_name)).all()
