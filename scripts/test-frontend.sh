#!/usr/bin/env bash
# Frontend lint + type-check + production build in a node:22 container (as CI
# does). Also sidesteps Windows npm choking on the "&" in this folder's path.
# Uses a container-only node_modules volume so it never fights a host install.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

MSYS_NO_PATHCONV=1 docker run --rm \
  -v "$ROOT/frontend:/app" -w /app \
  -v due-brew-node-modules:/app/node_modules \
  -v due-brew-npm-cache:/root/.npm \
  node:22-slim sh -c "${NPM_INSTALL:-npm ci} --no-audit --no-fund --loglevel=error \
    && npm run lint && npm run typecheck && npm run build"
