#!/usr/bin/env bash
# Pull-based deploy, run periodically on the Pi (see due-brew-deploy.timer).
# Deploys origin/main once GitHub CI has passed for that exact commit. It only
# makes outbound requests, so nothing on the Pi needs to be reachable from GitHub.
set -euo pipefail

REPO_DIR="${REPO_DIR:-$HOME/due-brew}"
GITHUB_REPO="${GITHUB_REPO:-Yatheesh-Nagella/due-brew}"
GITHUB_API="${GITHUB_API:-https://api.github.com}"
BRANCH="${BRANCH:-main}"
STATE_DIR="${STATE_DIR:-$HOME/.due-brew-deploy}"
PROXY_HEALTH_URL="${PROXY_HEALTH_URL:-http://localhost/due-brew/api/health}"
HEALTH_RETRIES="${HEALTH_RETRIES:-10}"
HEALTH_RETRY_DELAY="${HEALTH_RETRY_DELAY:-3}"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

# Prints one of: success | pending | failure
ci_state() {
  curl -fsS -H "Accept: application/vnd.github+json" \
    "$GITHUB_API/repos/$GITHUB_REPO/commits/$1/check-runs" |
    python3 -c '
import json, sys
runs = json.load(sys.stdin)["check_runs"]
if not runs or any(r["status"] != "completed" for r in runs):
    print("pending")
elif all(r["conclusion"] in ("success", "skipped") for r in runs):
    print("success")
else:
    print("failure")
'
}

# Every step is checked explicitly: errexit is disabled inside functions that
# are called from an `if`, so relying on `set -e` here would hide failures.
deploy_stack() {
  docker compose build || return 1
  docker compose up -d --wait db || return 1
  # Migrate before swapping containers: if this fails, the old version keeps running.
  docker compose run --rm --no-deps api alembic upgrade head || return 1
  # --wait blocks until the api's own healthcheck passes; no host port is
  # published, so the end-to-end check below goes through Caddy.
  docker compose up -d --wait || return 1
  curl -fsS --retry "$HEALTH_RETRIES" --retry-delay "$HEALTH_RETRY_DELAY" --retry-all-errors \
    "$PROXY_HEALTH_URL" >/dev/null || return 1
}

main() {
  mkdir -p "$STATE_DIR"
  exec 9>"$STATE_DIR/lock"
  if ! flock -n 9; then
    log "another deploy is already running"
    return 0
  fi

  cd "$REPO_DIR"
  git fetch --quiet origin "$BRANCH"
  local target deployed failed state
  target=$(git rev-parse "origin/$BRANCH")
  deployed=$(cat "$STATE_DIR/deployed" 2>/dev/null || true)
  failed=$(cat "$STATE_DIR/failed" 2>/dev/null || true)

  if [ "$target" = "$deployed" ]; then
    return 0
  fi
  if [ "$target" = "$failed" ]; then
    return 0 # already tried and failed; wait for a new commit
  fi

  state=$(ci_state "$target")
  if [ "$state" != "success" ]; then
    log "CI is $state for ${target:0:7}; not deploying"
    return 0
  fi

  log "deploying ${target:0:7} (previously ${deployed:0:7})"
  if ! git checkout --quiet "$BRANCH" || ! git merge --quiet --ff-only "origin/$BRANCH"; then
    log "FAILED: cannot fast-forward $BRANCH to ${target:0:7}"
    echo "$target" >"$STATE_DIR/failed"
    return 1
  fi

  if deploy_stack; then
    echo "$target" >"$STATE_DIR/deployed"
    rm -f "$STATE_DIR/failed"
    log "deployed ${target:0:7}"
  else
    echo "$target" >"$STATE_DIR/failed"
    log "FAILED deploying ${target:0:7}; last good commit: ${deployed:-none}"
    log "fix forward on main, or roll back with: git checkout <good-sha> && docker compose up -d --build"
    return 1
  fi
}

# Wrapped in a function so bash has read the whole script before the git merge
# above can replace this very file.
main "$@"
exit 0
