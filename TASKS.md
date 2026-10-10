# TASKS

The working tracker for Due and Brew. `claude.md` is the spec; this file is
where we are against it. Claude updates it as work lands, and you can add to
it anytime (drop a line under **Inbox** and it gets picked up).

**Legend**: `[x]` done and tested · `[ ]` to do · `[~]` built, waiting on an
owner step · 🧪 = the test(s) that prove it · 👤 = only the owner can do it

**Current milestone: M0 (skeleton)**: code done and tested locally; waiting
on the owner steps below to deploy it.

## Inbox

_Add tasks, bugs or ideas here; they get triaged into a milestone._

- 

## How to run the tests

| Command | What it checks | Last run |
|---|---|---|
| `bash scripts/test-backend.sh` | ruff lint + format, pytest on Python 3.12 against a throwaway Postgres 16 | 2026-10-10: 18 passed |
| `bash scripts/test-frontend.sh` | oxlint, `tsc` type-check, production build (node 22) | 2026-10-10: pass |
| `bash scripts/e2e-local.sh` | whole stack in Docker behind a real Caddy using `ops/caddy/due-brew.caddy` | 2026-10-10: 12/12 checks |
| `bash deploy/test/test_deploy.sh` (Linux/CI) | deploy script vs fake GitHub API and fake docker | 2026-10-10: 24/24 checks |

All four run in containers, so they behave the same on the laptop, in CI and
for the Pi's images. (Windows npm can't run scripts from a folder with `&` in
its name, which is another reason the frontend checks run in Docker.)

## M0: Skeleton deployed

- [x] Compose with `web`, `api`, `notifier`, `db`; one Python package
      (`backend/due_brew`) shared by api and notifier
- [x] Alembic set up; migration `0001` creates `users` + `notifier_heartbeat`;
      api runs `alembic upgrade head` on start
      🧪 `test_migrations.py::test_models_match_migrations`
- [x] `get_current_user` reads `Tailscale-User-Login`, fails closed:
      missing header → 401, unknown login → 403, `DEV_USER_LOGIN` only outside
      production, unset `APP_ENV` counts as production
      🧪 `test_identity.py` (9 tests), e2e "alice/bob header reaches the API"
- [x] `GET /api/me` returns the right housemate for each login
      🧪 `test_identity.py::test_each_housemate_gets_themselves`
- [x] `GET /api/health`: DB status + notifier heartbeat age (no identity needed)
      🧪 `test_health.py`, e2e "health through Caddy"
- [x] Notifier loop (heartbeat only for now), `--once` CLI, clean SIGTERM stop
      🧪 `test_health.py::test_health_reports_heartbeat_age`, e2e "--once"
- [x] Clock: `NOW_OVERRIDE` (ignored in production), "today" in `TZ`
      🧪 `test_clock.py`
- [x] Seed users from `SEED_USERS` on api start; insert-only, never
      overwrites Settings edits   🧪 `test_seed.py`
- [x] Frontend shell: four-tab bottom nav (List, Inventory, Bills, Settings),
      "Hi, name", not-recognized screen, Settings shows identity + system status
- [x] Caddy snippet `ops/caddy/due-brew.caddy` (strips `/due-brew` like
      recipe-box); verified locally that headers pass through unchanged
      🧪 `scripts/e2e-local.sh`
- [x] CI: ruff, pytest (Postgres service), frontend lint/type-check/build,
      compose build **for arm64 under QEMU**, shellcheck + deploy tests
- [x] Deploy: `deploy/deploy.sh` + `due-brew-deploy.{service,timer}` copied
      from recipe-box (no host port, so the post-deploy check goes through Caddy)
- [~] 👤 Push to GitHub and turn on branch protection (see Owner steps)
- [~] 👤 First deploy on the Pi + Caddy route + `install.sh` (see `DEPLOY.md`)
- [ ] Verify `/due-brew` loads on the tailnet and `/me` is right **from both
      housemates' phones**: this is the real proof that `tailscale serve` sends
      the header (see Risk 1 below)
- [ ] CI green on GitHub, including the arm64 build (first run happens on push)

## M1: Grocery and inventory ledger

- [ ] Migration: `categories`, `items` (status check needed/have/low,
      added_by/updated_by FKs); seed default categories
- [ ] Categories CRUD   🧪 create/rename/delete, unique name, delete with items
- [ ] Items CRUD + filters (`status`, `category_id`)   🧪 CRUD, filters
- [ ] Quick add (name only → `needed`)   🧪
- [ ] Duplicate guard: same name (case-insensitive) flips the existing item
      to `needed`   🧪 `"Milk"` then `"milk"` → one row, status needed
- [ ] `GET /grocery-list`: needed+low grouped by category, Need before Low   🧪
- [ ] `POST /items/{id}/bought` → have; `POST /items/{id}/add-to-list` → needed   🧪
- [ ] added_by/updated_by set from `get_current_user`   🧪 two users, check both fields
- [ ] Frontend: List page (quick add, grouped list, one-tap bought, Low badge)
- [ ] Frontend: Inventory page (filters, inline status toggles, Add to list)
- [ ] "added by Alex" shown in the UI
- [ ] 👤 Both housemates use it from their phones

## M2: Bills without reminders

- [ ] Migration: `bills`, `bill_assignees`, `bill_occurrences`, `reminder_rules`
- [ ] Recurrence engine (pure function)   🧪 monthly/quarterly/yearly/once,
      due_day 29–31 in short months, leap years, end_date cut-off
- [ ] Bills CRUD with assignees + reminder rules (defaults 3 and 0; API accepts 0–30)   🧪
- [ ] Occurrence generation on bill save (horizon 60 days), idempotent   🧪
- [ ] `GET /bills/upcoming?days=`: upcoming + overdue unpaid   🧪
- [ ] Mark paid / undo; variable amount on occurrence   🧪
- [ ] Delete with paid history requires confirmation; deactivate preferred   🧪
- [ ] Frontend: Bills page; home-page summary strip

## M3: Email reminders

- [ ] Migration: `notification_log` (+ `claimed_at`), unique indexes incl.
      partial digest index
- [ ] `EmailSender` interface, SMTP impl (587 STARTTLS), fake for tests, dry run
- [ ] Jinja2 templates (text + HTML), subjects per spec
- [ ] Tick: generate → find due → claim (`ON CONFLICT DO NOTHING`) → send → record
- 🧪 Notifier tests (all with `NOW_OVERRIDE` + fake sender):
  - [ ] right day and hour; paid gets none
  - [ ] two ticks in a row send nothing twice
  - [ ] stale pending re-sent after `STALE_PENDING_MINUTES`; two concurrent
        ticks can't both re-claim it
  - [ ] catch-up within 48h (marked late), older skipped + logged
  - [ ] digest grouping incl. overdue; individual-mode single overdue email
  - [ ] retry with backoff, give up after 5
- [ ] `PATCH /me`, `GET /notifications`, `POST /notifications/test`
- [ ] Settings page: preferences, send test email, notification log
- [ ] 👤 Gmail account + app password; real test email received by both

## M4: Hardening

- [ ] `DEPLOY.md` complete: backup + restore of the Postgres volume (tested restore)
- [ ] 👤 One week of real use with no duplicate or missed reminders

## Owner steps (👤): what only you can do

1. **Create the GitHub repo** `Yatheesh-Nagella/due-brew` (public), then from
   this folder: `git remote add origin … && git push -u origin main`.
   The deploy script assumes that exact repo name (`GITHUB_REPO` in `deploy/deploy.sh`).
2. **Branch protection on `main`** like recipe-box: require a PR + the four
   checks (`backend`, `frontend`, `compose`, `deploy-script`), no bypass,
   approvals **off**.
3. **Pi first deploy**: follow `DEPLOY.md`.
4. **Roommate on the tailnet**, and tell Claude their Tailscale login + email
   for `SEED_USERS` (or put them straight into the Pi's `.env`).

## Decisions made where the spec was silent

Each one is easy to change; say so if you disagree.

| # | Decision | Why |
|---|---|---|
| 1 | Name: **Due and Brew**, path `/due-brew`, package `due_brew` | owner, 2026-10-03 |
| 2 | Caddy **strips** `/due-brew`; API serves `/api/*`; uvicorn `--root-path /due-brew` so the `/api/docs` links work | "copy recipe-box exactly" |
| 3 | UUID primary keys | recipe-box convention |
| 4 | Frontend in **TypeScript** (else same stack as recipe-box) | spec requires a type-check in CI |
| 5 | Extra table `notifier_heartbeat` (single row) beyond the spec's eight | heartbeat has to live somewhere both containers see; a table is the boring choice |
| 6 | Missing header → **401**, unknown login → **403**; `/api/health` is the one route without identity | deploy script + Docker healthcheck have no Tailscale identity; health reveals only up/down |
| 7 | `APP_ENV` defaults to **production** when unset | fail closed |
| 8 | Seed runs on every api start, insert-only | so `.env` changes land without a manual step, but never clobber Settings edits |
| 9 | Defaults: `notify_mode=individual`, `digest_hour=8` | open decision in spec; change anytime |
| 10 | Network aliases `due-brew-api` / `due-brew-web` on `caddy_webnet` | `api`/`web` are generic enough to collide with another app later |
| 11 | No host ports at all (recipe-box publishes `127.0.0.1:8000`) | spec says so; post-deploy health check goes through Caddy instead |
| 12 | Deploy timer **every 6h**, copied from recipe-box | spec says 5 min, but you slowed recipe-box to 6h on purpose. Change `OnUnitInactiveSec` if you want faster deploys while building |
| 13 | psycopg 3 (`postgresql+psycopg://`) | spec's `DATABASE_URL`; recipe-box uses psycopg2 |

## Risks / things to verify on the real Pi

1. **Identity header from `tailscale serve`.** Locally we proved Caddy passes
   the header through; we have *not* yet seen `tailscale serve` set it. It is
   only added for requests from **user-owned** devices (not tagged devices),
   and a node-shared roommate may show up differently. First check after
   deploy: open Settings on each phone and confirm the login shown. If it
   says "Not recognized", the screen is working as designed: look at what
   login was sent (`docker compose logs api`) and put that in `SEED_USERS`.
2. **Header spoofing.** Only `tailscale serve` should be setting
   `Tailscale-User-Login`. Caddy is bound to `127.0.0.1`, so only the Pi
   itself could forge it. Acceptable for a two-person tailnet app; noted.
3. **arm64 build time under QEMU** in CI may be slow (npm + pip under
   emulation). Fine if it stays under ~15 min.
