#!/usr/bin/env bash
# Sync this repo to the server and (re)start the container. No registry needed.
#   deploy/push.sh user@host            # code
#   deploy/push.sh user@host --infra    # first deploy / domain change: also installs the Caddy
#                                       # site file into /srv/caddy/sites and reloads Caddy
# .env is copied as-is (it holds the tokens); it is never committed.
set -euo pipefail
HOST=${1:?usage: deploy/push.sh user@host [--infra]}
DEST=/srv/budget-box
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "no .env (copy .env.example)"; exit 1; }
DOMAIN=$(sed -n 's/^DOMAIN=//p' .env | cut -d' ' -f1)

rsync -az --delete --exclude .git --exclude .venv --exclude __pycache__ --exclude .pytest_cache \
  --exclude .DS_Store ./ "$HOST:$DEST/"
ssh "$HOST" "chmod 600 $DEST/.env && cd $DEST && docker compose -f deploy/compose.yaml up -d --build \
  && docker compose -f deploy/compose.yaml ps"

if [[ "${2:-}" == "--infra" ]]; then
  : "${DOMAIN:?set DOMAIN in .env}"
  sed "s/{\$DOMAIN}/$DOMAIN/" deploy/budgetbox.caddy | ssh "$HOST" "cat > /srv/caddy/sites/budgetbox.caddy"
  ssh "$HOST" "cd /srv/caddy && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile"
fi
echo "live: https://${DOMAIN:-<DOMAIN>}/healthz"
