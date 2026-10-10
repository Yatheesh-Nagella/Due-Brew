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

## Later sections (to be completed)

- M3: create the house Gmail account + app password, fill SMTP values, send a test email
- M4: back up and restore the Postgres volume
