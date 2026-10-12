#!/usr/bin/env bash
# Run the whole app on this laptop, behind Caddy like on the Pi, at
# http://localhost:8080/due-brew/ in development mode (you are Alice), with
# emails caught by a local Mailpit inbox at http://localhost:8025.
# Data persists between runs in its own Docker volume.
#   scripts/run-local.sh             # build + start (or restart after code changes)
#   scripts/run-local.sh --as bob    # act as Bob instead
#   scripts/run-local.sh logs        # follow api + notifier logs
#   scripts/run-local.sh stop        # stop everything (keeps data)
#   scripts/run-local.sh reset       # stop and delete local data
# With ops/local/smtp.env present (see smtp.env.example), emails go out for
# real through that SMTP server instead of Mailpit, and the notifier is
# stopped so only Settings -> "Send test email" sends.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CADDY=due-brew-local-caddy
URL=http://localhost:8080/due-brew/
# Own Caddy network: a shared one would let another due-brew stack (e.g. the
# e2e run) answer to the same due-brew-api alias.
export COMPOSE_PROJECT_NAME=due-brew-local DUE_BREW_ENV_FILE=ops/local/local.env CADDY_NETWORK=due-brew-local-web

compose() { docker compose -f "$ROOT/docker-compose.yml" -f "$ROOT/ops/local/mailpit.compose.yml" "$@"; }

case "${1:-}" in
  stop)
    docker rm -f "$CADDY" >/dev/null 2>&1 || true
    compose stop
    exit 0
    ;;
  reset)
    docker rm -f "$CADDY" >/dev/null 2>&1 || true
    compose down -v --remove-orphans
    exit 0
    ;;
  logs)
    compose logs -f api notifier
    exit 0
    ;;
  --as)
    # Override the dev identity for this run; compose's environment beats env_file.
    export DEV_USER_LOGIN="${2:?usage: --as alice|bob}@example.com"
    ;;
esac

docker network inspect "$CADDY_NETWORK" >/dev/null 2>&1 || docker network create "$CADDY_NETWORK" >/dev/null
SMTP_FILE="$ROOT/ops/local/smtp.env"
if [ -n "${DEV_USER_LOGIN:-}" ] || [ -f "$SMTP_FILE" ]; then
  # Build a temporary env file (gitignored) from local.env plus overrides.
  tmp="$ROOT/ops/local/.local-override.env"
  cp "$ROOT/ops/local/local.env" "$tmp"
  if [ -n "${DEV_USER_LOGIN:-}" ]; then
    sed -i "s/^DEV_USER_LOGIN=.*/DEV_USER_LOGIN=$DEV_USER_LOGIN/" "$tmp"
  fi
  if [ -f "$SMTP_FILE" ]; then
    # Drop the keys smtp.env sets, then append it, so its values win.
    keys=$(grep -oE '^[A-Z_]+=' "$SMTP_FILE" | tr -d '=' | paste -sd'|' -)
    grep -vE "^(${keys})=" "$tmp" >"$tmp.next" || true
    cat "$tmp.next" "$SMTP_FILE" >"$tmp"
    rm -f "$tmp.next"
  fi
  export DUE_BREW_ENV_FILE=ops/local/.local-override.env
fi
compose up -d --build --wait
if [ -f "$SMTP_FILE" ]; then
  # Local test bills belong to fake @example.com users; don't let reminders
  # bounce off a real SMTP account.
  compose stop notifier >/dev/null 2>&1
fi

docker rm -f "$CADDY" >/dev/null 2>&1 || true
MSYS_NO_PATHCONV=1 docker run -d --name "$CADDY" --network "$CADDY_NETWORK" -p 127.0.0.1:8080:80 \
  -v "$ROOT/ops/e2e/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v "$ROOT/ops/caddy/due-brew.caddy:/etc/caddy/due-brew.caddy:ro" \
  caddy:2 >/dev/null
for _ in $(seq 1 30); do curl -fs "${URL}api/health" >/dev/null 2>&1 && break; sleep 1; done

echo
echo "Due and Brew is running: $URL"
echo "  API docs:  ${URL}api/docs"
if [ -f "$SMTP_FILE" ]; then
  echo "  email:     REAL, via $(grep -E '^SMTP_HOST=' "$SMTP_FILE" | cut -d= -f2) (ops/local/smtp.env); notifier stopped"
  echo "             set your real address in Settings, then press Send test email"
else
  echo "  inbox:     http://localhost:8025  (every email the app sends lands here)"
fi
echo "  logs:      scripts/run-local.sh logs"
echo "  stop:      scripts/run-local.sh stop"
