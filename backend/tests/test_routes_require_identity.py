from fastapi.routing import APIRoute

from due_brew.api.main import app
from due_brew.identity import get_current_user

# Routes that deliberately run without a Tailscale identity.
PUBLIC = {"/api/health"}


def _depends_on(dependant, target) -> bool:
    return any(d.call is target or _depends_on(d, target) for d in dependant.dependencies)


def test_every_route_requires_identity():
    unguarded = [
        f"{sorted(route.methods)} {route.path}"
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path not in PUBLIC
        and not _depends_on(route.dependant, get_current_user)
    ]
    assert unguarded == []
