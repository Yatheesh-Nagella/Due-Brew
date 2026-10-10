from fastapi import FastAPI

from due_brew.api.routers import health, users

# Caddy strips /due-brew before forwarding, so routes live at /api/* here.
# Uvicorn's --root-path /due-brew lets the OpenAPI docs build correct links.
app = FastAPI(title="Due and Brew", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.include_router(health.router)
app.include_router(users.router)
