# DEPLOY

First-time setup of Due and Brew on the Pi. Everything here is run **by the
owner on the Pi**; Claude never runs commands there. This covers
M0 through M3 (email is section 6); backup/restore comes in M4.

## 1. Clone and configure

```bash
cd ~
git clone https://github.com/Yatheesh-Nagella/due-brew.git   # HTTPS + lowercase: the timer expects ~/due-brew
cd due-brew
cp .env.example .env
nano .env
```

In `.env`, set at least:

- `POSTGRES_PASSWORD`: something random, **and the same value inside
  `DATABASE_URL`** (`openssl rand -hex 24` works).
- `SEED_USERS`: `login:Name:email` for both housemates, commas only *between*
  people, no spaces, e.g.
  `Alice-Smith@github:Alice:alice@example.com,BobJones@github:Bob:bob@example.com`.
  Exact logins (case matters) are on login.tailscale.com/admin/users, or run
  `tailscale whois <device-ip> | grep -i login` on the Pi. The login is the
  person's Tailscale login name (what the admin console shows, e.g.
  `someone@gmail.com` or `someone@github`).
- `APP_ENV=production`, `TZ=America/Chicago`.

Leave the SMTP values as placeholders until M3.

## 2. Add the Caddy route

Paste the contents of [`ops/caddy/due-brew.caddy`](ops/caddy/due-brew.caddy)
into `~/caddy/Caddyfile`, inside the same site block as the recipe-box
routes, **before** any catch-all (`/` homepage) handler. Then validate and
**restart** Caddy:

```bash
cd ~/caddy
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile
docker compose restart caddy
docker compose exec caddy grep -c due-brew /etc/caddy/Caddyfile   # > 0
```

Restart, not just `caddy reload`: the Caddyfile is mounted into the container
as a single file, and editors like vim save by replacing the file, so the
container keeps seeing the old copy and a reload silently re-applies the old
routes (that's what happened on the first deploy: `/due-brew/...` returned the
homepage's 404). The `grep` proves the container sees the new routes.

Add a card to the homepage (`~/caddy/homepage/index.html`):

```html
  <li><a href="/due-brew/">Due and Brew<small>Groceries and house bills</small></a></li>
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

## 6. Email reminders (Brevo)

Reminders go out through **Brevo**'s SMTP relay (free plan: 300 emails a day;
two housemates use a handful). The app only speaks standard SMTP, so any
provider works by changing `.env` (Gmail alternative at the end of this
section).

### Set up Brevo (once)

1. Sign up at **brevo.com** (free plan). Finish any profile/company questions
   it asks; new accounts can't send until that's done, and occasionally Brevo
   reviews a new account before enabling sending. If sending fails with an
   "account not activated / under review" error, that's why: contact their
   support or wait.
2. **Verify a sender**: Brevo → **Senders, domains & dedicated IPs** →
   **Senders** → **Add a sender**. Name it "Due and Brew" and use an email
   address you can read (e.g. your Gmail); Brevo emails it a code to confirm.
   Reminders will come *from* this address.
3. **Get the SMTP credentials**: Brevo → **SMTP & API** → **SMTP** tab. Note
   the **SMTP server** (`smtp-relay.brevo.com`), **port** (`587`) and your
   **login** (shown there, often like `abc123@smtp-brevo.com`; it's not
   necessarily your account email). Click **Generate a new SMTP key**, name it
   "Due and Brew", and copy it. It's shown once. (It's an **SMTP key**, not an
   API key.)

### Optional: try it from the laptop first

On the laptop, copy `ops/local/smtp.env.example` to `ops/local/smtp.env`
(gitignored), fill in the values, and run `bash scripts/run-local.sh`. In
http://localhost:8080/due-brew/settings set your **real** email, Save, then
**Send test email**. This proves the Brevo side works before the Pi is
involved. Delete `ops/local/smtp.env` afterwards to go back to Mailpit.

### Put it on the Pi

In `~/due-brew/.env` on the Pi (`nano .env`, save with Ctrl+O, Enter,
Ctrl+X):

```bash
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_USERNAME=abc123@smtp-brevo.com            # the SMTP login from step 3
SMTP_PASSWORD=xsmtpsib-...                      # the SMTP key from step 3
EMAIL_FROM=Due and Brew <you@gmail.com>         # the sender verified in step 2
NOTIFIER_DRY_RUN=false
APP_BASE_URL=https://raspberrypi.tailb66afe.ts.net/due-brew
```

Then:

```bash
chmod 600 .env
docker compose up -d --force-recreate api notifier
docker compose logs notifier --tail 5    # "... SMTP via smtp-relay.brevo.com"
```

### Test from both phones

1. Open **https://raspberrypi.tailb66afe.ts.net/due-brew/settings**, check the
   **Email** field is your real address (fix it and Save if not).
2. **Send test email**. It should arrive within a minute or two.
3. First time: **check spam**, mark it "Not spam" and add the sender to your
   contacts. Mail sent through a relay "from" a gmail.com address is more
   likely to be filtered at first; this trains your inbox. Brevo's
   **Transactional → Logs** page shows whether it was delivered, bounced or
   blocked.
4. Your housemate does the same. When both have it, M3's last box is done.

### If the test email fails

The reason shows under the button and in the Settings notification log.

| Error mentions | Fix |
|---|---|
| `535` / authentication failed | `SMTP_USERNAME` must be the SMTP **login** from the SMTP tab, `SMTP_PASSWORD` the **SMTP key** (not the account password, not an API key). Recreate api + notifier after editing. |
| sender not valid / not verified | `EMAIL_FROM` must use the exact address verified in step 2. |
| account not activated / suspended / under review | Finish the Brevo account setup or contact Brevo support. |
| timeout / connection refused | The Pi can't reach Brevo: `docker compose exec notifier python -c "import socket; socket.create_connection(('smtp-relay.brevo.com', 587), 5); print('ok')"` |
| "sent" but nothing arrived | Spam folder, then Brevo → Transactional → Logs. |

Security: the SMTP key lives only in the Pi's `.env` (gitignored, `chmod
600`). If it leaks, delete it in Brevo → SMTP & API and generate a new one.
Don't paste it into chats or commits.

### Alternative: Gmail

With a Gmail account that has 2-Step Verification, create an app password at
myaccount.google.com/apppasswords and use `SMTP_HOST=smtp.gmail.com`,
`SMTP_USERNAME` and the address in `EMAIL_FROM` = that Gmail address,
`SMTP_PASSWORD` = the app password without spaces.

How reminders behave (details in `claude.md` and `TASKS.md` decisions 20-25):

- Sent at each person's chosen hour, by default 3 days before and on the
  due date; one overdue email the morning after if it's still unpaid
  (digest users see overdue bills in the digest for up to 7 days).
- If the Pi was off, reminders up to 48 hours late are still sent, marked
  "(late)"; older ones are logged as skipped, never sent days late.
- A failed send is retried after 5, 15, 45 and 120 minutes, then given up
  and shown as failed in the log.
- Never sent twice, with one deliberate exception: if the Pi crashes in the
  instant after the SMTP server accepted an email but before it was recorded, that one
  email is sent again on recovery.

To pause all emails (e.g. while testing), set `NOTIFIER_DRY_RUN=true` and
recreate the notifier: it then logs what it would send instead.

## Later sections (to be completed)

- M4: back up and restore the Postgres volume
