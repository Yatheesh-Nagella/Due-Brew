#!/usr/bin/env bash
# Run the whole app on this laptop, behind Caddy like on the Pi, at
# http://localhost:8080/due-brew/ in development mode (you are Alice).
# Data persists between runs in its own Docker volume.
#   scripts/run-local.sh             # build + start (or restart after code changes)
#   scripts/run-local.sh --as bob    # act as Bob instead
#   scripts/run-local.sh logs        # follow api + notifier logs
#   scripts/run-local.sh stop        # stop everything (keeps data)
#   scripts/run-local.sh reset       # stop and delete local data
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CADDY=due-brew-local-caddy
URL=http://localhost:8080/due-brew/
export COMPOSE_PROJECT_NAME=due-brew-local DUE_BREW_ENV_FILE=ops/local/local.env

compose() { docker compose -f "$ROOT/docker-compose.yml" "$@"; }

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

docker network inspect caddy_webnet >/dev/null 2>&1 || docker network create caddy_webnet >/dev/null
if [ -n "${DEV_USER_LOGIN:-}" ]; then
  # Rewrite the identity into a temporary env file so containers pick it up.
  tmp="$ROOT/ops/local/.local-override.env"
  sed "s/^DEV_USER_LOGIN=.*/DEV_USER_LOGIN=$DEV_USER_LOGIN/" "$ROOT/ops/local/local.env" >"$tmp"
  export DUE_BREW_ENV_FILE=ops/local/.local-override.env
fi
compose up -d --build --wait

docker rm -f "$CADDY" >/dev/null 2>&1 || true
MSYS_NO_PATHCONV=1 docker run -d --name "$CADDY" --network caddy_webnet -p 127.0.0.1:8080:80 \
  -v "$ROOT/ops/e2e/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v "$ROOT/ops/caddy/due-brew.caddy:/etc/caddy/due-brew.caddy:ro" \
  caddy:2 >/dev/null
for _ in $(seq 1 30); do curl -fs "${URL}api/health" >/dev/null 2>&1 && break; sleep 1; done

echo
echo "Due and Brew is running: $URL"
echo "  API docs:  ${URL}api/docs"
echo "  logs:      scripts/run-local.sh logs"
echo "  stop:      scripts/run-local.sh stop"
