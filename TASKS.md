# TASKS

The working tracker for Due and Brew. `claude.md` is the spec; this file is
where we are against it. Claude updates it as work lands, and you can add to
it anytime (drop a line under **Inbox** and it gets picked up).

**Legend**: `[x]` done and tested · `[ ]` to do · `[~]` built, waiting on an
owner step · 🧪 = the test(s) that prove it · 👤 = only the owner can do it

**Live on the Pi since 2026-10-12.** M0–M3 merged and deployed; auto-deploy
timer installed. Open: the housemate's first login, test emails from the Pi on both
phones, then M4 (backups + a week of real use).

## Inbox

_Add tasks, bugs or ideas here; they get triaged into a milestone._

- 

## How to run the tests

| Command | What it checks | Last run |
|---|---|---|
| `bash scripts/test-backend.sh` | ruff lint + format, pytest on Python 3.12 against a throwaway Postgres 16 | 2026-10-10: 182 passed |
| `bash scripts/run-local.sh` | not a test: runs the app at http://localhost:8080/due-brew/ as Alice (`--as bob`, `stop`, `reset`, `logs`); emails land in http://localhost:8025 | |
| `bash scripts/test-frontend.sh` | oxlint, `tsc` type-check, production build (node 22) | 2026-10-10: pass |
| `bash scripts/e2e-local.sh` | whole stack in Docker behind a real Caddy using `ops/caddy/due-brew.caddy` | 2026-10-10: 29/29 checks |
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
- [x] 👤 Pushed to GitHub (`Yatheesh-Nagella/Due-Brew`); PRs #1–#4 merged through CI
- [ ] 👤 Branch protection on `main` (require PR + the four checks), if not done yet
- [x] 👤 First deploy on the Pi (2026-10-12): `~/due-brew`, Caddy route,
      homepage card, `install.sh` timer running
- [x] `/due-brew` loads on the tailnet and greets the owner by name from
      their phone: `tailscale serve` → Caddy → API identity works end to end
- [ ] Same from the housemate's phone (invited as a tailnet user)
- [x] CI green on GitHub, including the arm64 build
- First-deploy lessons (now in `DEPLOY.md`): clone over HTTPS into lowercase
  `~/due-brew`; `DATABASE_URL` must carry `POSTGRES_PASSWORD`; `SEED_USERS` is
  `login:Name:email` with logins like `Someone@github`; Caddy mounts the single
  Caddyfile, so after editing with vim **restart** Caddy (reload kept the old file)

## M1: Grocery and inventory ledger

Built ahead of the M0 Pi deploy at the owner's request (2026-10-10), on
branch `feature/m1-grocery-ledger`.

- [x] Migration `0002`: `categories` (seeded: Produce, Dairy, Meat & Fish,
      Bakery, Pantry, Frozen, Drinks, Cleaning, Toiletries, Household) and
      `items` (status check, `quantity >= 0`, added_by/updated_by FKs)
      🧪 `test_categories.py::test_migration_seeds_default_categories`, migration drift test
- [x] Categories CRUD; delete leaves its items uncategorized; reorder; 409 on
      duplicate names   🧪 `test_categories.py` (7 tests)
- [x] Items CRUD + filters (`status`, `category_id`), PATCH changes only sent
      fields, blank text stored as null   🧪 `test_items.py`
- [x] Quick add (name only → Need)   🧪 `test_quick_add_creates_a_needed_item`
- [x] Duplicate guard via unique index on `lower(name)` + `INSERT … ON
      CONFLICT`: 201 new / 200 merged, keeps original spelling, safe under
      concurrent adds   🧪 `test_duplicate_*`, `test_concurrent_quick_adds_make_one_row`,
      e2e "merged, not duplicated"
- [x] `GET /grocery-list`: Need + Low, grouped by category (or store,
      case-insensitive), Need before Low, counts   🧪 `test_grocery_list.py` (5 tests)
- [x] `POST /items/{id}/bought` → Have; `/add-to-list` → Need   🧪 `test_bought_and_add_to_list`
- [x] added_by / updated_by from `get_current_user`   🧪 `test_patch_changes_only_sent_fields_and_records_editor`
- [x] Every route except `/api/health` requires identity
      🧪 `test_routes_require_identity.py` (guards future routes too)
- [x] `GET /users` (for M2 assignee pickers)
- [x] List page: summary strip, quick add, grouped list (Aisle / Store
      toggle, remembered), Low badge, big "✓ Bought" button with **Undo** toast,
      "already in inventory" notice when the duplicate guard merges
- [x] Inventory page: search, category + status filters, inline Need/Low/Have
      toggle, "Add to list" on Have items, tap an item to edit every field or
      delete it, "+ Add item" form, Categories section (add, rename, ↑↓, delete)
- [x] "added by Alice · updated by Bob" shown on every item
- [ ] 👤 Try it locally (`bash scripts/run-local.sh`) and say what to change
- [ ] 👤 Both housemates use it from their phones (after the Pi deploy)
- Ideas, not committed to: suggest a category on quick add from past items;
  swipe-to-buy on the List page

## M2: Bills without reminders

On branch `feature/m2-bills` (stacked on M1).

- [x] Recurrence engine `due_brew/recurrence.py` (pure functions)
      🧪 `test_recurrence.py` (19): monthly, quarterly, yearly, once; due_day
      28–31 in every short month; Feb 29 in leap / non-leap years; start and
      end dates inclusive; windows across year boundaries
- [x] Migration `0003`: `bills`, `bill_assignees`, `bill_occurrences`
      (unique bill + due date), `reminder_rules` (0–30, unique per bill),
      check constraints mirroring the API rules
- [x] Bills CRUD with assignees (≥1) and reminder days (default 3 and 0,
      API accepts 0–30, deduped)   🧪 `test_bills.py` create/edit/invalid (12 invalid cases)
- [x] Occurrence generation `bills.sync_occurrences`: runs on bill save and
      before bill listings (so the 60-day horizon rolls forward without the
      notifier); edits move unpaid future rows, never paid ones; idempotent
      🧪 `test_changing_due_day_moves_unpaid_but_keeps_paid`,
      `test_horizon_rolls_forward_as_days_pass`, `test_syncing_twice_changes_nothing`
- [x] Deactivate (hides it, drops future unpaid rows, reactivating restores);
      delete with paid history → 409 unless `confirm=true`
      🧪 `test_deactivate_*`, `test_delete_with_paid_history_needs_confirmation`
- [x] `GET /bills/upcoming?days=`: due in window (paid or not) + overdue unpaid,
      active bills only   🧪 `test_upcoming_window_overdue_and_paid`, `test_overdue_stays_until_paid`
- [x] Mark paid / undo (second "paid" keeps the first payer)   🧪 `test_mark_paid_and_undo`
- [x] Variable amounts on the occurrence; one-off overrides survive a bill
      amount change   🧪 `test_variable_bill_amount_on_occurrence`, `test_override_survives_bill_amount_change`
- [x] Dates are local calendar dates in `TZ`   🧪 `test_due_dates_are_plain_dates_in_local_tz`
- [x] Bills page: Overdue section, next 30 days with **✓ Paid** / Undo,
      "Set amount" on variable bills, all bills with schedule text
      ("Monthly on the 1st"), next due, assignees, Inactive badge; tap to edit
- [x] Bill editor: amount (blank = varies), repeats, due day (29–31 notes
      "or last day of month"), month for yearly, start/end dates, assignees,
      reminders as pre-checked "3 days before" + "On due date" with
      "+ Add reminder" offering 1, 2, 5, 7 days; Active toggle; two-step delete
- [x] Home summary strip: "5 items to buy · 2 bills this week" linking to
      Bills, red when something's overdue
- [x] e2e: create bill, upcoming, mark paid, undo through Caddy
- [ ] 👤 Try it locally and merge the PR

## M3: Email reminders

On branch `feature/m3-reminders`. Planned at 33 points in 9 commits; done in
those 9 plus a line-endings cleanup.

| # | Commit | Points |
|---|---|---|
| 1 | `notification_log` table + idempotency indexes | 2 |
| 2 | EmailSender: SMTP, dry run, fake | 2 |
| 3 | Jinja2 templates + spec subjects | 3 |
| 4 | Reminder planner (pure) | 5 |
| 5 | Claim / send / record, retries, digests | 8 |
| 6 | Notifier tick in the worker + Mailpit | 3 |
| 7 | `PATCH /me`, `/notifications`, test email API | 3 |
| 8 | Settings page | 5 |
| 9 | Docs | 2 |

- [x] Migration `0004`: `notification_log` with `claimed_at`, partial unique
      indexes (reminder: occurrence+rule+user; overdue: occurrence+user;
      digest: user+day)   🧪 `test_notification_log.py`
- [x] `EmailSender` interface; SMTP (STARTTLS + login), dry run (no bodies,
      no password in logs), fake   🧪 `test_email_sender.py`
- [x] Templates text + HTML; subjects per spec, "(late)", "amount not set"
      🧪 `test_email_compose.py`
- [x] Planner: right day + user's hour, 48h catch-up, skip older, overdue
      window, email on/off, DST day   🧪 `test_planner.py` (14)
- 🧪 Notifier tests the spec requires (`test_notifier.py`, real Postgres):
  - [x] right day and hour; every assignee; paid gets none; deactivated / email off gets none
  - [x] two ticks in a row send nothing twice
  - [x] a crash-left pending claim is re-sent once after STALE_PENDING_MINUTES;
        8 concurrent reclaimers → exactly 1 wins; 6 concurrent claimers → 1 row
  - [x] catch-up within 48h sent "(late)"; older skipped + logged
  - [x] digest grouping incl. overdue; overdue repeats daily for 7 days in
        digests; individual mode gets one overdue email; mode switch doesn't repeat
  - [x] retry with backoff; give up after 5; paid-before-retry → skipped
  - [x] sabotage check: removing the stale cutoff fails 10 tests, removing
        ON CONFLICT fails 6
- [x] Notifier container runs real ticks; `--once`; heartbeat each tick
- [x] `PATCH /me`, `GET /notifications`, `POST /notifications/test`
      🧪 `test_settings_api.py`
- [x] Settings page: preferences, send test email, System status (heartbeat
      "running" / "not running?"), notification log
- [x] Mailpit inbox for local runs (http://localhost:8025), never on the Pi
- [x] e2e through Caddy + real SMTP into Mailpit: bill due today → two ticks →
      exactly one email; test email; log (29/29)
- [x] `DEPLOY.md` §6: Brevo SMTP setup (Gmail as an alternative), test email, how reminders behave
- [ ] 👤 Brevo account, verified sender and SMTP key on the Pi; a real test email received
      by both housemates
- [ ] 👤 No duplicate or missed reminders over the first real week (M4)

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
| 14 | Quarterly bills repeat every 3 months **counting from the start date's month** | spec only gives due_day; the editor says so |
| 15 | One-off bills are due on their **start date** (due_day is set from it) | spec has no separate date field for "once" |
| 16 | Occurrences generate from **7 days back** through the horizon | a bill entered just after its due date should show as overdue; older ones don't flood the list |
| 17 | Occurrence `amount` NULL means "use the bill's amount" | bill amount edits flow to future dues; variable bills and one-off overrides set it explicitly |
| 18 | Occurrences also sync when bills are listed, not only on save | otherwise the 60-day horizon goes stale until the notifier arrives in M3 |
| 19 | Upcoming/overdue shows only **active** bills; overdue shows until paid (the 7-day limit applies to reminder emails) | deactivating should stop the nagging |
| 20 | Individual-mode overdue email: **once**, the morning after the due date (at the user's hour), any time within 7 days | owner, 2026-10-10 |
| 21 | New log kind **`overdue`** (spec lists reminder / digest) with its own unique index | so an overdue email can't repeat; owner, 2026-10-10 |
| 22 | Retry backoff **5, 15, 45, 120 min**, give up after the 5th attempt | owner, 2026-10-10 |
| 23 | Switching email mode mid-day never repeats an email already sent that day | both modes share the reminder rows; owner, 2026-10-10 |
| 24 | A reminder for a bill that's already overdue is **skipped**, not sent late | the overdue email covers it; avoids "due 1 day ago" |
| 25 | Digests list overdue bills daily for up to 7 days; no digest on days with nothing to say | spec: "plus overdue unpaid occurrences" |
| 26 | Log columns beyond the spec: `next_attempt_at` (backoff), `digest_id` (items in a digest), `subject` (log view) | needed for retries and a readable log |
| 27 | Mailpit, local/e2e only (`ops/local/mailpit.compose.yml`) | owner approved, 2026-10-10; never in the Pi's compose |
| 28 | Local stacks use their own Caddy network (`CADDY_NETWORK`) | two stacks on one network shared the due-brew-api alias and cross-talked |
| 29 | Repo-wide LF line endings (`.gitattributes`) | CRLF had crept in from Windows |
| 30 | Email via **Brevo** SMTP relay (free, 300/day), not a house Gmail account | Google refused a new account ("phone number used too many times"); owner, 2026-10-12. Config-only: any SMTP provider works |
| 31 | `ops/local/smtp.env` (gitignored) makes the laptop send real email; the local notifier is stopped then | test the provider before the Pi exists, without bouncing reminders off fake @example.com users |

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
