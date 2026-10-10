"""Who is making this request. The only module that reads identity headers.

Tailscale Serve adds Tailscale-User-Login to every request it proxies, and
Caddy passes it through to the API. Everything else receives a User from
Depends(get_current_user) and never looks at headers itself.
"""

import logging

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from due_brew import models
from due_brew.config import get_settings
from due_brew.database import get_db

log = logging.getLogger("uvicorn.error")

LOGIN_HEADER = "Tailscale-User-Login"


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User:
    settings = get_settings()
    login = (request.headers.get(LOGIN_HEADER) or "").strip()
    if not login and not settings.is_production:
        login = settings.dev_user_login or ""
    if not login:
        # Fail closed: never fall back to a default user.
        raise HTTPException(status_code=401, detail="No Tailscale identity on this request")

    user = db.scalar(select(models.User).where(models.User.tailscale_login == login))
    if user is None:
        # Logged so the owner can see which login to add to SEED_USERS.
        log.warning("rejected unknown Tailscale login %r", login)
        raise HTTPException(status_code=403, detail="This Tailscale login is not a housemate")
    return user
