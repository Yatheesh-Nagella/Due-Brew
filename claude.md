Due and Brew - what's due, and what's in the kitchen.

Mission
Build Due and Brew (slug due-brew, Python package due_brew): a self-hosted web app that two housemates use to keep a shared ledger of household items to buy and to get email reminders for house bills. It runs on a Raspberry Pi 5 in Docker, reachable only over Tailscale. Name decided by the owner on 2026-10-03.
Instructions to the agent:
• Treat this doc as the spec. Where it is silent, follow the patterns of the existing recipe-box repo rather than inventing new ones.
• Work milestone by milestone (see Milestones). Finish each milestone's acceptance criteria, with tests passing, before starting the next.
• When a decision listed under Open decisions blocks you, ask the owner instead of guessing.
• Email is the only notification channel. Do not add SMS, WhatsApp or push code paths.
Existing environment
The Pi already hosts one app, recipe-box, with the same stack and deploy path this app should use. Read that repo before writing code.
Piece
Current state
Host
Raspberry Pi 5 (arm64), headless, SSH user lol
Containers
Docker; every image must support arm64
Network access
Tailscale only; Caddy published via tailscale serve --bg at https://raspberrypi.tailb66afe.ts.net/
Reverse proxy
Caddy in Docker, routing by path; config lives in its own repo, github.com/Yatheesh-Nagella/caddy-config
Reference app
github.com/Yatheesh-Nagella/recipe-box: React (Vite) served by nginx, FastAPI, Postgres, Alembic migrations, routed at /recipe-box and /recipe-box/api
Deploy
A systemd timer on the Pi polls GitHub every 5 minutes and pulls/rebuilds only after CI has passed on that commit
Repo visibility
Public on GitHub, so no secrets in git, ever
Workflow rules:
• Claude Code runs on the owner's laptop only. Never run commands on the Pi; it is a deploy-only target reached by push to GitHub, then the timer's pull and Docker rebuild.
• Changes to caddy-config or the systemd timer are written as files or instructions for the owner to apply, not applied directly.
Scope
Version 1 is a two-user app: a shared shopping/inventory ledger plus bill tracking with email reminders.
In scope:
• Household items: add, edit, categorize, mark as needed / have / low, and a grocery list view built from them.
• Bills: recurring and one-off, assigned to one or both housemates, with per-occurrence "paid" tracking.
• Email reminders before and on the due date, as individual emails or a daily digest, per user preference.
• A notification history view under Settings showing what was sent, to whom, and whether it failed.
Out of scope for v1:
• SMS, WhatsApp, push or any channel other than email.
• Public internet exposure; the app is reachable only through the tailnet.
• A username/password login system; identity comes from Tailscale (see Architecture).
• Payments, bank connections, receipt scanning, or bill splitting math beyond recording who a bill is assigned to.
• Integration with recipe-box (a later idea, not v1).
Architecture
Four containers in one docker-compose.yml: a web frontend, an API, a notifier worker and Postgres. The API and notifier share one Python package so models and business logic live in one place.
Container
Built from
Job
web
React + Vite, served by nginx
UI, mounted under /due-brew
api
FastAPI (Python 3.12)
REST API under /due-brew/api; runs Alembic migrations on start
notifier
Same Python package as api, different entrypoint
Loop that generates bill occurrences and sends reminder emails
db
postgres:16 (arm64)
Data store with a named volume
Routing and base paths:
• Caddy routes /due-brew/api/* to api and /due-brew/* to web, mirroring recipe-box. Copy recipe-box's approach to Vite base, nginx config and API path prefix exactly.
• No container publishes ports to the host except through Caddy's Docker network. Join whatever network recipe-box uses to reach Caddy.
Identity (no login system):
• Tailscale Serve adds identity headers such as Tailscale-User-Login to proxied requests. The API reads that header, matches it to a row in users, and rejects requests whose login is unknown (HTTP 403).
• Verify early that Caddy forwards these headers unchanged to api. If the header is missing, fail closed, never fall back to a default user in production.
• For local development only, DEV_USER_LOGIN in the environment supplies a fake login. It must be ignored when APP_ENV=production.
• The roommate must be on the tailnet (invited as a user or via node sharing) for this to work. Confirming that is an owner task, not code.
All identity resolution lives in one FastAPI dependency, get_current_user, used as Depends(get_current_user) on every route. Business logic receives a User object and never reads request headers. The Tailscale header lookup and the development override live only inside this dependency, and tests override it instead of faking headers.
Data model
Eight tables, all created through Alembic migrations. Every table gets id, created_at and updated_at; money is NUMERIC(10,2); due dates are DATE, never timestamps.
Table
Key fields
Notes
users
tailscale_login (unique), display_name, email, notify_mode (individual / digest), digest_hour (0–23), email_enabled
Seeded by a migration or a seed script from env; two rows in v1
categories
name (unique), sort_order
e.g. Produce, Dairy, Cleaning, Toiletries
items
name, category_id, quantity, unit, status (needed / have / low), store, notes, added_by, updated_by
Grocery list = items with status needed or low
bills
name, amount (nullable for variable bills), recurrence (monthly / quarterly / yearly / once), due_day (1–31), due_month (for yearly), start_date, end_date (nullable), active, notes
Assignees in the next table
bill_assignees
bill_id, user_id (composite unique)
One or both housemates
bill_occurrences
bill_id, due_date, amount, paid_at, paid_by
Unique on (bill_id, due_date); one row per due instance
reminder_rules
bill_id, days_before (0 = due day)
Defaults 3 and 0 when a bill is created; unique on (bill_id, days_before)
notification_log
occurrence_id, rule_id (nullable for digests), user_id, kind (reminder / digest), digest_date, status (pending / sent / failed / skipped), attempts, last_error, claimed_at, sent_at
Uniqueness rules below make sending idempotent
Idempotency constraints on notification_log:
• Individual reminders: unique on (occurrence_id, rule_id, user_id).
• Digests: unique on (user_id, digest_date) where kind = 'digest' (a partial unique index).
Due-day edge case: a due_day larger than the month's length (e.g. 31 in February) resolves to the month's last day.
Feature specs
Grocery and inventory ledger
• Status meanings (UI labels Need / Have / Low; database values stay needed / have / low):
    ◦ Need: on the grocery list.
    ◦ Low: also on the grocery list, but not urgent; shown below Need items with a "Low" badge.
    ◦ Have: in stock and off the list.
• Quick add: a single text box that creates an item with status needed; category and quantity are optional and editable later.
• Grocery list view: items with status needed or low, grouped by category (optionally by store), with a one-tap "bought" action that sets status to have.
• Inventory view: all items, filterable by category and status, with inline status toggles and an "Add to list" button on Have items that sets them to Need via POST /items/{id}/add-to-list.
• Record added_by and updated_by from the request's identity and show them in the UI ("added by Alex").
• Duplicate guard: adding an item whose name matches an existing one (case-insensitive) flips that item back to needed instead of creating a second row.
Bills
• Create, edit, deactivate and delete bills. Deleting a bill with paid history requires confirmation; prefer deactivating.
• Each bill shows its next occurrence, amount, assignees and paid status.
• "Mark paid" on an occurrence sets paid_at and paid_by. Undo is allowed. Paid occurrences get no further reminders.
• Variable bills (amount null on the bill) let the user enter the amount on the occurrence; reminders say "amount not set" until then.
• Reminder rules are editable per bill. The API accepts any days_before from 0 to 30, but the UI stays simple: "3 days before" and "On due date" as pre-checked boxes, plus an "Add reminder" control offering 1, 2, 5 and 7 days before.
Reminders
• A reminder email goes to every assignee of the bill, on each rule's day, at that user's digest_hour.
• Users with notify_mode = digest get at most one email per day listing everything with a reminder that day, plus overdue unpaid occurrences.
• Overdue unpaid occurrences (due date passed, not paid) appear in that day's digest, or get a single overdue email in individual mode, for up to 7 days after the due date.
• Every email includes the bill name, amount (or "amount not set"), due date, assignees, and a link to the app's bills page on the tailnet URL.
Notifier worker
The notifier is a long-running Python process that wakes every NOTIFIER_INTERVAL_SECONDS (default 300) and runs one tick. It must be safe to restart at any moment and must never send the same reminder twice.
Each tick, in order:
1. Generate occurrences. For every active bill, upsert bill_occurrences rows for all due dates from today through OCCURRENCE_HORIZON_DAYS (default 60) ahead. The unique key makes this repeatable.
2. Find due reminders. For each unpaid occurrence, rule and assignee, compute the send date (due_date - days_before). It is due when the send date is today or within the catch-up window, and the user's local hour is at or past their digest_hour.
3. Claim before sending. Insert a notification_log row with status pending using INSERT ... ON CONFLICT DO NOTHING. Rows to send are: rows this tick actually inserted, failed rows eligible for retry, and stale pending rows whose claim is older than STALE_PENDING_MINUTES (default 10), which a crash left behind. Re-claim stale rows atomically (UPDATE ... WHERE status = 'pending' AND claimed_at < cutoff RETURNING) so two ticks cannot both take one.
4. Send. Individual mode sends one email per claimed row; digest mode groups the user's claimed rows for the day into one email under a single digest log row.
5. Record the result. Set sent with sent_at, or failed with attempts + 1 and last_error. Retry failed rows on later ticks with backoff, up to 5 attempts.
Delivery guarantee: at-least-once. A crash after the SMTP server accepts an email but before the row is marked sent can cause one duplicate on recovery. That is deliberate: a rare duplicate reminder is better than a silently missed bill. Add a claimed_at column to notification_log for this.
Catch-up: if the Pi was off, reminders whose send date fell within the last CATCHUP_HOURS (default 48) and have no log row are still sent, marked late in the subject. Older missed ones are skipped and logged as skipped, never sent days late.
Email delivery:
• SMTP through Brevo's free SMTP relay (decided 2026-10-12; Google blocked creating a house Gmail account): smtp-relay.brevo.com, port 587, STARTTLS, Brevo SMTP login + SMTP key, from a verified sender address. Any SMTP provider works through the same env vars. Use the standard library smtplib or aiosmtplib.
• Send multipart emails: plain text plus simple HTML, rendered from Jinja2 templates in the repo.
• Subjects: [due-brew] Rent due in 3 days ($1,200 on Oct 1); digests: [due-brew] 2 bills need attention today.
• All SMTP calls go through an EmailSender interface so tests can swap in a fake.
Testing hooks:
• NOTIFIER_DRY_RUN=true logs the emails it would send instead of sending them.
• NOW_OVERRIDE (ISO datetime) replaces the clock, so a tick can simulate any date. Ignore it when APP_ENV=production.
• A CLI command python -m due_brew.notifier --once runs a single tick and exits, for manual tests.
• The notifier writes a heartbeat timestamp each tick; the API's health endpoint reports it, so a dead notifier is visible in the UI.
API and frontend
All endpoints sit under /due-brew/api, return JSON, and require a known Tailscale identity. FastAPI's generated OpenAPI docs stay enabled (the app is tailnet-only).
Method and path
Purpose
GET /me
Current user from the identity header
PATCH /me
Update own email, notify mode, digest hour
GET /users
Both housemates (for assignee pickers)
GET/POST /items, PATCH/DELETE /items/{id}
Item CRUD; GET filters by status, category_id
GET /grocery-list
Items with status needed or low, grouped by category, Need before Low
POST /items/{id}/bought
Set status to have
POST /items/{id}/add-to-list
Set status to needed
GET/POST /categories, PATCH/DELETE /categories/{id}
Category CRUD
GET/POST /bills, GET/PATCH/DELETE /bills/{id}
Bill CRUD, including assignees and reminder rules
GET /bills/upcoming?days=30
Occurrences due soon plus overdue unpaid ones
POST /occurrences/{id}/paid, DELETE /occurrences/{id}/paid
Mark paid / undo
PATCH /occurrences/{id}
Set amount on a variable bill's occurrence
GET /notifications?limit=50
Notification log, newest first
POST /notifications/test
Send a test email to the current user
GET /health
DB status and notifier heartbeat age
Frontend pages (React Router, mobile-first, since phones are the main client):
• List (home page): a one-line summary strip at the top ("5 items to buy · 2 bills this week", the second part linking to Bills), then the grocery list with quick add and "bought" taps. The strip uses the existing /grocery-list and /bills/upcoming?days=7 endpoints; no dashboard, no charts.
• Inventory: all items with filters, status toggles and "Add to list".
• Bills: upcoming and overdue occurrences at top, mark-paid buttons, then all bills with edit forms.
• Settings: own email, notify mode, digest hour, a "send test email" button, and a System status section with the notifier heartbeat and the notification log.
Primary navigation has exactly four items: List, Inventory, Bills, Settings. Groceries and bills stay separate screens.
Use the same UI libraries and styling approach as recipe-box unless they make this harder; keep the bundle small.
Configuration and secrets
All configuration comes from environment variables loaded from a .env file on the Pi. The repo contains only .env.example with placeholder values, and .gitignore must exclude .env.
Variable
Example
Used by
APP_ENV
production / development
api, notifier
TZ
America/Chicago
all containers
DATABASE_URL
postgresql+psycopg://...
api, notifier
POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
—
db
APP_BASE_URL
https://raspberrypi.tailb66afe.ts.net/due-brew
notifier (links in emails)
SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD
smtp-relay.brevo.com, 587, Brevo SMTP login, SMTP key
notifier, api (test email)
EMAIL_FROM
Due and Brew <house address>
notifier
SEED_USERS
login1:Name1:email1,login2:Name2:email2
seed script
NOTIFIER_INTERVAL_SECONDS, OCCURRENCE_HORIZON_DAYS, CATCHUP_HOURS, STALE_PENDING_MINUTES
300, 60, 48, 10
notifier
NOTIFIER_DRY_RUN, NOW_OVERRIDE, DEV_USER_LOGIN
—
development and tests only
Time rules:
• Store due dates as DATE and compare against "today" in TZ, so a bill due on the 1st is due on the 1st locally.
• Store event times (paid_at, sent_at) as TIMESTAMPTZ in UTC; convert to TZ only for display.
• Never log the SMTP password or full email bodies at info level.
Testing, CI and deployment
The deploy timer only ships commits whose CI passed, so CI is the release gate and must be meaningful.
Tests (pytest, against a real Postgres in CI via a service container):
• Recurrence: monthly, quarterly, yearly and one-off dates; due_day 29–31 in short months; leap years; end_date cut-off.
• Notifier: reminders fire on the right day and hour; paid occurrences get none; two ticks in a row send nothing twice; a claim left pending by a simulated crash is re-sent once it is older than STALE_PENDING_MINUTES, and two concurrent ticks cannot both re-claim it; catch-up sends within 48 hours and skips older; digest grouping; retry and give-up after 5 failures. Use NOW_OVERRIDE and the fake EmailSender.
• API: identity header required, unknown login gets 403, DEV_USER_LOGIN ignored in production, item duplicate guard, mark paid / undo.
• Frontend: lint, type-check and production build must pass; component tests are optional in v1.
CI (GitHub Actions on every push and PR): Python lint (ruff), tests, frontend lint and build, and docker compose build for arm64 via QEMU/buildx so an image that fails on the Pi fails in CI first.
Deployment deliverables for the owner to apply:
• The Caddy route block for /due-brew and /due-brew/api, as a ready-to-paste snippet or a PR description for caddy-config.
• The change needed so the existing systemd deploy timer also covers this repo (follow how it handles recipe-box).
• A DEPLOY.md with first-time steps: create .env from .env.example, set up Brevo SMTP (or another provider), seed users, run migrations, send a test email, and how to back up the Postgres volume.
Milestones
Five milestones, each deployable on its own. Do not start one until the previous one's boxes are all ticked.
M0: Skeleton deployed
[ ] Repo scaffolded: web, api, notifier, db in compose; shared Python package; Alembic set up
[ ] GET /health works and the web page loads at /due-brew through Caddy on the tailnet
[ ] Identity header read and GET /me returns the right housemate for both people
[ ] CI green, including the arm64 build; deploy timer picks the repo up
M1: Grocery and inventory ledger
[ ] Items and categories CRUD, grocery list (Need above Low), quick add, "bought", "Add to list", duplicate guard
[ ] added_by / updated_by shown in the UI
[ ] Both housemates have used it from their phones
M2: Bills without reminders
[ ] Bills, assignees, reminder rules and occurrence generation (run from the API on bill save for now)
[ ] Upcoming/overdue view, mark paid / undo, variable amounts, and the home-page summary strip
[ ] Recurrence tests pass, including month-end and leap-year cases
M3: Email reminders
[ ] Notifier container running ticks, with heartbeat visible in the UI
[ ] Individual and digest modes, catch-up, retries, notification log under Settings, System status
[ ] Settings page with "send test email"; a real test email received by both housemates
[ ] Idempotency tests pass (double tick, stale pending recovery)
M4: Hardening
[ ] DEPLOY.md complete, including Postgres backup and restore steps
[ ] One week of real use with no duplicate or missed reminders
Guardrails and open decisions
Guardrails for the agent:
• Never commit .env, credentials, real email addresses or Tailscale logins. Use placeholders in examples and tests.
• Never run anything on the Pi or push to caddy-config; produce files and instructions instead.
• Never add a notification channel other than email.
• Never let the API fall back to a default user when the identity header is missing in production.
• Prefer boring, well-known libraries; ask before adding any new service or container beyond the four listed.
Open decisions for the owner:
[x] Final app name and URL path (decided: "Due and Brew", path /due-brew)
[ ] Reuse recipe-box's Postgres container with a separate database, or run a dedicated db container (decided: dedicated)
[ ] Roommate's Tailscale login and email address, for SEED_USERS
[x] Email provider: Brevo SMTP relay instead of a house Gmail account (decided 2026-10-12)
[ ] Brevo account created, sender verified, SMTP key generated
[ ] Default reminder rules (spec assumes 3 days before and on the due day) and default digest hour