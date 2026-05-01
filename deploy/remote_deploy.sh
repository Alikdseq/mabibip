#!/usr/bin/env bash
set -euo pipefail

# Remote deploy helper (F10.1.2)
#
# Expects:
# - docker compose available on host
# - GHCR auth already done (docker login ghcr.io) or registry is public
# - .env present in DEPLOY_PATH (server-specific secrets)
#
# Optional:
# - APP_REF (tag) to deploy; if set, you can use it in compose image tags.

echo "Deploying in $(pwd)"

docker compose pull
docker compose up -d --remove-orphans
docker compose ps

