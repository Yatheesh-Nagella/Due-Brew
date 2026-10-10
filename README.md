# Due and Brew

What's due, and what's in the kitchen. A self-hosted app for two housemates:
a shared grocery/inventory list plus house-bill tracking with email
reminders. Runs on a Raspberry Pi 5 in Docker, reachable only over Tailscale
at `/due-brew`.

- **Spec**: [`claude.md`](claude.md)
- **Progress, tests, decisions**: [`TASKS.md`](TASKS.md)
- **First-time Pi setup**: [`DEPLOY.md`](DEPLOY.md)

## Layout

```
docker-compose.yml        db · api · notifier · web
backend/
  due_brew/               shared package: models, identity, clock, seed
    api/                  FastAPI app (routes under /api)
    notifier/             worker: python -m due_brew.notifier [--once]
  migrations/             Alembic
  tests/                  pytest, real Postgres
frontend/                 React + Vite + TypeScript, served by nginx
deploy/                   pull-based deployer + systemd timer (as in recipe-box)
ops/caddy/                route snippet for the Pi's Caddyfile
ops/e2e/                  local Caddy + env for scripts/e2e-local.sh
scripts/                  test-backend.sh · test-frontend.sh · e2e-local.sh
```

## Local development

```bash
bash scripts/run-local.sh         # the app at http://localhost:8080/due-brew/ (you are Alice)
bash scripts/run-local.sh --as bob   # same, as Bob · `stop` · `reset` · `logs`
bash scripts/test-backend.sh      # ruff + pytest (Docker)
bash scripts/test-frontend.sh     # lint + type-check + build (Docker)
bash scripts/e2e-local.sh         # full stack behind Caddy; KEEP=1 to leave it up
```

`KEEP=1 bash scripts/e2e-local.sh` serves the app at
<http://localhost:8088/due-brew/>. Browsers don't send the Tailscale
header, so the UI shows "Not recognized" there; use `curl -H
"Tailscale-User-Login: alice@example.com"` or set `APP_ENV=development` and
`DEV_USER_LOGIN` in `ops/e2e/e2e.env`.
