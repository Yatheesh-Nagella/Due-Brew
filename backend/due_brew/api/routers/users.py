from fastapi import APIRouter, Depends

from due_brew import models, schemas
from due_brew.identity import get_current_user

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
def get_me(user: models.User = Depends(get_current_user)):
    return user
