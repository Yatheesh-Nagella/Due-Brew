# DEPLOY

First-time setup of Due and Brew on the Pi. Everything here is run **by the
owner on the Pi**; Claude never runs commands there. This covers M0;
Gmail, test email and backup/restore sections are completed in M3/M4.

## 1. Clone and configure

```bash
cd ~
git clone https://github.com/Yatheesh-Nagella/due-brew.git
cd due-brew
cp .env.example .env
nano .env
```

In `.env`, set at least:

- `POSTGRES_PASSWORD`: something random, **and the same value inside
  `DATABASE_URL`** (`openssl rand -hex 24` works).
- `SEED_USERS`: `login:Name:email` for both housemates. The login is the
  person's Tailscale login name (what the admin console shows, e.g.
  `someone@gmail.com` or `someone@github`).
- `APP_ENV=production`, `TZ=America/Chicago`.

Leave the SMTP values as placeholders until M3.

## 2. Add the Caddy route

Paste the contents of [`ops/caddy/due-brew.caddy`](ops/caddy/due-brew.caddy)
into `~/caddy/Caddyfile`, inside the same site block as the recipe-box
routes, **before** any catch-all (`/` homepage) handler. Then reload Caddy:

```bash
cd ~/caddy
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile
# (or: docker compose restart caddy)
```

If `~/caddy` is the `caddy-config` repo, commit the change there too.

## 3. Start the stack

```bash
cd ~/due-brew
docker compose up -d --build --wait     # first arm64 build takes a few minutes
docker compose ps                       # db, api, notifier, web all up
curl -fsS http://localhost/due-brew/api/health
```

Migrations run automatically when `api` starts, and the users from
`SEED_USERS` are created then too.

## 4. Check identity from both phones

Open `https://raspberrypi.tailb66afe.ts.net/due-brew/` on each phone. The
header should say "Hi, <name>" and **Settings** should show that person's
Tailscale login.

If a phone shows **"Not recognized"**, see what login actually arrived:

```bash
docker compose logs api | grep -E "api/me|unknown Tailscale login"
```

- `rejected unknown Tailscale login '…'` (403): fix that person's login in `SEED_USERS`, then
  `docker compose restart api` (the seed runs on start and is insert-only; it adds the new login).
- 401: no header arrived at all. Check the device isn't a *tagged* device
  and that the request goes through `tailscale serve`, not straight to the Pi's IP.

## 5. Turn on automatic deploys

```bash
cd ~/due-brew
sudo ./deploy/install.sh
systemctl list-timers due-brew-deploy.timer
journalctl -u due-brew-deploy -n 50
```

Same mechanism as recipe-box: it deploys `origin/main` only after every
GitHub check on that commit has passed. State lives in `~/.due-brew-deploy/`.

Manual fallback: `cd ~/due-brew && git pull && docker compose up -d --build`.

## 6. Email reminders (Gmail)

Reminders go out from a dedicated house Gmail account through an **app
password**. Never use the account's real password: an app password can only
send mail and can be revoked on its own.

1. Create (or pick) the house Gmail account.
2. Turn on **2-Step Verification** for it (Google Account → Security). App
   passwords only exist once 2-Step Verification is on.
3. Google Account → Security → **App passwords** (or visit
   `myaccount.google.com/apppasswords`), create one called "Due and Brew",
   and copy the 16-character password.
4. On the Pi, in `~/due-brew/.env`:

   ```bash
   SMTP_HOST=smtp.gmail.com
   SMTP_PORT=587
   SMTP_STARTTLS=true
   SMTP_USERNAME=the-house-account@gmail.com
   SMTP_PASSWORD=abcdefghijklmnop        # the app password, spaces removed
   EMAIL_FROM=Due and Brew <the-house-account@gmail.com>
   NOTIFIER_DRY_RUN=false
   APP_BASE_URL=https://raspberrypi.tailb66afe.ts.net/due-brew
   ```

5. Restart so the api and notifier read it:
   `docker compose up -d --force-recreate api notifier`
6. On each phone: **Settings → Send test email**. It should arrive within a
   minute (check spam the first time and mark it "not spam"). If it fails,
   the reason is shown right there and in the notification log.
7. Check the notifier is ticking: **Settings → System status** should say
   "running", and `docker compose logs notifier` should show
   `ticking every 300s; SMTP via smtp.gmail.com`.

How reminders behave (details in `claude.md` and `TASKS.md` decisions 20-25):

- Sent at each person's chosen hour, by default 3 days before and on the
  due date; one overdue email the morning after if it's still unpaid
  (digest users see overdue bills in the digest for up to 7 days).
- If the Pi was off, reminders up to 48 hours late are still sent, marked
  "(late)"; older ones are logged as skipped, never sent days late.
- A failed send is retried after 5, 15, 45 and 120 minutes, then given up
  and shown as failed in the log.
- Never sent twice, with one deliberate exception: if the Pi crashes in the
  instant after Gmail accepted an email but before it was recorded, that one
  email is sent again on recovery.

To pause all emails (e.g. while testing), set `NOTIFIER_DRY_RUN=true` and
recreate the notifier: it then logs what it would send instead.

## Later sections (to be completed)

- M4: back up and restore the Postgres volume
