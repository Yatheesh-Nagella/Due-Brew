from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from due_brew import models, schemas
from due_brew.database import get_db
from due_brew.identity import get_current_user

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
def get_me(user: models.User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[schemas.UserBrief])
def list_users(db: Session = Depends(get_db), _: models.User = Depends(get_current_user)):
    return db.scalars(select(models.User).order_by(models.User.display_name)).all()
