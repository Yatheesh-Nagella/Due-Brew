#!/usr/bin/env bash
# End-to-end smoke test of the real stack behind a real Caddy using the exact
# route snippet in ops/caddy/, on this laptop. Checks prefix stripping, the SPA,
# the API docs, the notifier heartbeat, and that Caddy passes the Tailscale
# identity header through untouched.
#   scripts/e2e-local.sh          # run, then tear everything down
#   KEEP=1 scripts/e2e-local.sh   # leave it running at http://localhost:8088/due-brew/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
E2E="$ROOT/ops/e2e"
PROJECT=due-brew-e2e
CADDY=due-brew-e2e-caddy
NET=due-brew-e2e-web  # its own Caddy network; see run-local.sh
URL=http://localhost:8088
# Separate compose project and env file, so a real .env is never touched.
export COMPOSE_PROJECT_NAME=$PROJECT DUE_BREW_ENV_FILE=ops/e2e/e2e.env MAILPIT_PORT=8026 CADDY_NETWORK=$NET
MAILPIT=http://localhost:8026

compose() { docker compose -f "$ROOT/docker-compose.yml" -f "$ROOT/ops/local/mailpit.compose.yml" "$@"; }

cleanup() {
  if [ -n "${KEEP:-}" ]; then
    echo "left running: $URL/due-brew/  (stop: docker rm -f $CADDY; COMPOSE_PROJECT_NAME=$PROJECT docker compose down -v)"
    return
  fi
  docker rm -f "$CADDY" >/dev/null 2>&1 || true
  compose down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker network inspect "$NET" >/dev/null 2>&1 || docker network create "$NET" >/dev/null
compose up -d --build --wait
docker rm -f "$CADDY" >/dev/null 2>&1 || true
MSYS_NO_PATHCONV=1 docker run -d --name "$CADDY" --network "$NET" -p 127.0.0.1:8088:80 \
  -v "$E2E/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v "$ROOT/ops/caddy/due-brew.caddy:/etc/caddy/due-brew.caddy:ro" \
  caddy:2 >/dev/null
for _ in $(seq 1 30); do curl -fs "$URL/due-brew/api/health" >/dev/null 2>&1 && break; sleep 1; done

FAILS=0
check() {
  local desc=$1
  shift
  if "$@"; then echo "  ok   $desc"; else echo "  FAIL $desc"; FAILS=$((FAILS + 1)); fi
}
status_of() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
body_has() { local needle=$1; shift; curl -fsS "$@" | grep -Eq -- "$needle"; }
login() { echo "Tailscale-User-Login: $1"; }

check "SPA served at /due-brew/" body_has '<title>Due and Brew</title>' "$URL/due-brew/"
check "SPA deep link falls back to index.html" body_has '<div id="root">' "$URL/due-brew/bills"
check "/due-brew redirects to /due-brew/" [ "$(status_of "$URL/due-brew")" = 308 ]
check "health through Caddy" body_has '"db":"ok"' "$URL/due-brew/api/health"
check "no identity header -> 401" [ "$(status_of "$URL/due-brew/api/me")" = 401 ]
check "unknown login -> 403" [ "$(status_of -H "$(login stranger@example.com)" "$URL/due-brew/api/me")" = 403 ]
check "alice's header reaches the API -> Alice" \
  body_has '"display_name":"Alice"' -H "$(login alice@example.com)" "$URL/due-brew/api/me"
check "bob's header reaches the API -> Bob" \
  body_has '"display_name":"Bob"' -H "$(login bob@example.com)" "$URL/due-brew/api/me"
check "OpenAPI docs point at the prefixed schema" body_has "/due-brew/api/openapi.json" "$URL/due-brew/api/docs"
check "OpenAPI schema reachable through Caddy" body_has '"/api/me"' "$URL/due-brew/api/openapi.json"
check "notifier has written a heartbeat" \
  bash -c "curl -fsS '$URL/due-brew/api/health' | grep -vq '\"notifier_heartbeat_age_seconds\":null'"
check "notifier --once runs a single tick" compose exec -T notifier python -m due_brew.notifier --once

as_alice=(-H "$(login alice@example.com)" -H "Content-Type: application/json")
check "quick add creates an item -> 201" \
  [ "$(status_of "${as_alice[@]}" -X POST -d '{"name":"Oat milk"}' "$URL/due-brew/api/items")" = 201 ]
check "same name again is merged, not duplicated -> 200" \
  [ "$(status_of "${as_alice[@]}" -X POST -d '{"name":"oat MILK"}' "$URL/due-brew/api/items")" = 200 ]
check "grocery list shows it, added by Alice" \
  body_has '"added_by_user":{"id":"[^"]*","display_name":"Alice"}' "${as_alice[@]}" "$URL/due-brew/api/grocery-list"
check "default categories were seeded" body_has '"name":"Produce"' "${as_alice[@]}" "$URL/due-brew/api/categories"

alice_id=$(curl -fsS "${as_alice[@]}" "$URL/due-brew/api/me" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
check "create a monthly bill -> 201 with defaults 3 and 0" body_has '"reminder_days":\[3,0\]' "${as_alice[@]}" \
  -X POST -d "{\"name\":\"Rent\",\"amount\":1200,\"recurrence\":\"monthly\",\"due_day\":1,\"assignee_ids\":[\"$alice_id\"]}" \
  "$URL/due-brew/api/bills"
occ_id=$(curl -fsS "${as_alice[@]}" "$URL/due-brew/api/bills/upcoming?days=45" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
check "upcoming lists the next rent" [ -n "$occ_id" ]
check "mark paid records Alice" body_has '"paid_by_user":\{"id":"[^"]*","display_name":"Alice"\}' "${as_alice[@]}" \
  -X POST "$URL/due-brew/api/occurrences/$occ_id/paid"
check "undo paid" body_has '"paid_at":null' "${as_alice[@]}" -X DELETE "$URL/due-brew/api/occurrences/$occ_id/paid"

# Reminders through the real notifier, real SMTP (to Mailpit) and real Postgres.
# Alice's reminder hour -> midnight, so "due today" fires whenever this runs.
compose exec -T db psql -q -U duebrew -d duebrew -c "UPDATE users SET digest_hour = 0" >/dev/null
check "one-off bill due today" body_has '"recurrence":"once"' "${as_alice[@]}" -X POST \
  -d "{\"name\":\"Plumber\",\"amount\":150,\"recurrence\":\"once\",\"assignee_ids\":[\"$alice_id\"],\"reminder_days\":[0]}" \
  "$URL/due-brew/api/bills"
check "notifier tick sends it" compose exec -T notifier python -m due_brew.notifier --once
check "notifier tick again" compose exec -T notifier python -m due_brew.notifier --once
mail_count() { curl -fsS "$MAILPIT/api/v1/messages" | grep -o 'Plumber due today' | wc -l | tr -d ' '; }
check "exactly one reminder email reached the inbox" [ "$(mail_count)" = 1 ]
check "addressed to Alice" body_has '"Address":"alice@example.com"' "$MAILPIT/api/v1/messages"

check "save preferences (digest at 7 PM)" body_has '"notify_mode":"digest","digest_hour":19' "${as_alice[@]}" \
  -X PATCH -d '{"notify_mode":"digest","digest_hour":19}' "$URL/due-brew/api/me"
check "send test email" body_has '"status":"sent"' "${as_alice[@]}" -X POST "$URL/due-brew/api/notifications/test"
check "test email reached the inbox" body_has 'Test email' "$MAILPIT/api/v1/messages"
check "notification log lists the reminder and the test" \
  body_has '"kind":"test".*"kind":"reminder"' "${as_alice[@]}" "$URL/due-brew/api/notifications"

echo
if [ "$FAILS" -ne 0 ]; then
  echo "$FAILS check(s) failed"
  compose logs --tail 30 api notifier
  exit 1
fi
echo "all e2e checks passed"
