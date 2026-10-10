#!/usr/bin/env bash
# Exercises deploy.sh against a local bare repo, a fake GitHub API and a fake docker.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEPLOY="$HERE/../deploy.sh"
T="$(mktemp -d)"
SERVER_PID=""
trap '[ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null; rm -rf "$T"' EXIT
PORT="${TEST_PORT:-18089}"

mkdir -p "$T/bin" "$T/web"
cat >"$T/bin/docker" <<'STUB'
#!/usr/bin/env bash
echo "docker $*" >>"$STUB_LOG"
if [ -n "${FAKE_DOCKER_FAIL:-}" ] && [[ "$*" == *"$FAKE_DOCKER_FAIL"* ]]; then exit 1; fi
STUB
chmod +x "$T/bin/docker"
export PATH="$T/bin:$PATH" STUB_LOG="$T/docker.log"

echo ok >"$T/web/health"
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$T/web" >/dev/null 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 50); do curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 0.1; done

export REPO_DIR="$T/deploy-clone" STATE_DIR="$T/state" GITHUB_REPO=o/r BRANCH=main
export GITHUB_API="http://127.0.0.1:$PORT"
export PROXY_HEALTH_URL="http://127.0.0.1:$PORT/health"
export HEALTH_RETRIES=0 HEALTH_RETRY_DELAY=0

git init -q --bare -b main "$T/origin.git"
git clone -q "$T/origin.git" "$T/dev" 2>/dev/null
git -C "$T/dev" config user.email t@example.com
git -C "$T/dev" config user.name tester
git -C "$T/dev" checkout -q -b main 2>/dev/null || true
echo v0 >"$T/dev/file"
git -C "$T/dev" add file
git -C "$T/dev" commit -qm v0
git -C "$T/dev" push -q origin main
git clone -q "$T/origin.git" "$REPO_DIR"

# From here on a failing check must be counted, not abort the run.
set +e

new_commit() {
  echo "$RANDOM$RANDOM" >>"$T/dev/file"
  git -C "$T/dev" commit -qam change
  git -C "$T/dev" push -q origin main
  git -C "$T/dev" rev-parse HEAD
}

set_ci() { # sha state
  local d="$T/web/repos/o/r/commits/$1"
  mkdir -p "$d"
  case "$2" in
    pending) echo '{"check_runs":[{"status":"in_progress","conclusion":null}]}' >"$d/check-runs" ;;
    empty) echo '{"check_runs":[]}' >"$d/check-runs" ;;
    success) echo '{"check_runs":[{"status":"completed","conclusion":"success"},{"status":"completed","conclusion":"success"}]}' >"$d/check-runs" ;;
    failure) echo '{"check_runs":[{"status":"completed","conclusion":"success"},{"status":"completed","conclusion":"failure"}]}' >"$d/check-runs" ;;
  esac
}

FAILS=0
check() { # description, then the command that must succeed
  local desc=$1
  shift
  if "$@"; then echo "  ok   $desc"; else echo "  FAIL $desc"; FAILS=$((FAILS + 1)); fi
}
status_is() { [ "$STATUS" -eq "$1" ]; }
status_not_zero() { [ "$STATUS" -ne 0 ]; }
state_is() { [ "$(state "$1")" = "$2" ]; }
state_empty() { [ -z "$(state "$1")" ]; }
docker_calls_are() { [ "$(docker_calls)" = "$1" ]; }

run() { # runs deploy.sh with a clean docker log; sets STATUS
  : >"$STUB_LOG"
  bash "$DEPLOY" >"$T/out.log" 2>&1
  STATUS=$?
}
docker_calls() { cat "$STUB_LOG"; }
no_docker_calls() { [ ! -s "$STUB_LOG" ]; }
state() { cat "$STATE_DIR/$1" 2>/dev/null || true; }

FULL_DEPLOY='docker compose build
docker compose up -d --wait db
docker compose run --rm --no-deps api alembic upgrade head
docker compose up -d --wait'

echo "CI not finished -> does nothing"
C1=$(new_commit)
set_ci "$C1" pending
run
check "exit 0" status_is 0
check "no docker calls (pending)" no_docker_calls
set_ci "$C1" empty
run
check "no docker calls (no check runs yet)" no_docker_calls

echo "CI failed -> does nothing"
set_ci "$C1" failure
run
check "exit 0" status_is 0
check "no docker calls (failed CI)" no_docker_calls
check "nothing recorded as deployed" state_empty deployed

echo "CI passed -> deploys in the right order"
set_ci "$C1" success
run
check "exit 0" status_is 0
check "build, postgres, migrate, up (in order)" docker_calls_are "$FULL_DEPLOY"
check "commit recorded as deployed" state_is deployed "$C1"
check "checkout advanced to the deployed commit" [ "$(git -C "$REPO_DIR" rev-parse HEAD)" = "$C1" ]

echo "Nothing new -> no-op"
run
check "exit 0" status_is 0
check "no docker calls" no_docker_calls

echo "Migration fails -> old containers keep running, failure remembered"
C2=$(new_commit)
set_ci "$C2" success
FAKE_DOCKER_FAIL="alembic" run
check "exit non-zero" status_not_zero
check "stopped before swapping containers" docker_calls_are "$(echo "$FULL_DEPLOY" | head -3)"
check "still marked as running the previous commit" state_is deployed "$C1"
check "failed commit recorded" state_is failed "$C2"
run
check "does not retry the same failed commit" status_is 0
check "no docker calls on retry" no_docker_calls

echo "Health check fails -> reported as failed"
C3=$(new_commit)
set_ci "$C3" success
PROXY_HEALTH_URL="http://127.0.0.1:$PORT/missing" run
check "exit non-zero" status_not_zero
check "not marked deployed" state_is deployed "$C1"
check "failed commit recorded" state_is failed "$C3"

echo "A new good commit after failures deploys and clears the failure"
C4=$(new_commit)
set_ci "$C4" success
run
check "exit 0" status_is 0
check "deployed" state_is deployed "$C4"
check "failure marker cleared" state_empty failed

echo
if [ "$FAILS" -ne 0 ]; then echo "$FAILS check(s) failed"; exit 1; fi
echo "all checks passed"
