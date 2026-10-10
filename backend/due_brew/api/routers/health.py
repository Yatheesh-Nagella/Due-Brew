from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from due_brew import clock, heartbeat, schemas
from due_brew.database import get_db

router = APIRouter(prefix="/api", tags=["health"])


# The one route without get_current_user: the deploy script and Docker
# healthcheck call it with no Tailscale identity, and it reveals nothing
# beyond "up or down".
@router.get("/health", response_model=schemas.HealthOut)
def health(response: Response, db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        last = heartbeat.last_beat(db)
    except Exception:
        response.status_code = 503
        return schemas.HealthOut(status="error", db="unreachable", notifier_heartbeat_age_seconds=None)

    age = (clock.now() - last).total_seconds() if last else None
    return schemas.HealthOut(status="ok", db="ok", notifier_heartbeat_age_seconds=age)
