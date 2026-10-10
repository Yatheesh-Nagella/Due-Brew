#!/usr/bin/env bash
# Run ruff + pytest in throwaway containers (python:3.12 + postgres:16), the
# same versions CI and the Pi use. Nothing touches the real app stack.
#   scripts/test-backend.sh               # everything
#   scripts/test-backend.sh -k identity   # extra args go to pytest
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NET=due-brew-test-net
DB=due-brew-test-db

cleanup() { docker rm -f "$DB" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" \
  -e POSTGRES_USER=duebrew -e POSTGRES_PASSWORD=test -e POSTGRES_DB=duebrew_test \
  postgres:16 >/dev/null
until docker exec "$DB" pg_isready -U duebrew -d duebrew_test >/dev/null 2>&1; do sleep 1; done

# MSYS_NO_PATHCONV stops Git Bash on Windows from rewriting /app into C:/...
MSYS_NO_PATHCONV=1 docker run --rm --network "$NET" \
  -v "$ROOT/backend:/app" -w /app \
  -e DATABASE_URL="postgresql+psycopg://duebrew:test@$DB:5432/duebrew_test" \
  -e PIP_DISABLE_PIP_VERSION_CHECK=1 -e PIP_ROOT_USER_ACTION=ignore \
  -v due-brew-pip-cache:/root/.cache/pip \
  python:3.12-slim sh -c "pip install -q -r requirements.txt -r requirements-dev.txt \
    && ruff check . && ruff format --check . && pytest -p no:cacheprovider $*"
