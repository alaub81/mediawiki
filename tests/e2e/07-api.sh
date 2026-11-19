#!/usr/bin/env bash
# Api.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# Read .env if present
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }
for _ in $(seq 1 30); do
  if curl -fsS "http://localhost:${MW_HTTP_PORT:-8080}/api.php?action=query&meta=siteinfo&format=json" | grep -q '"query"'; then
    echo "MediaWiki API OK"; exit 0
  fi
  sleep 3
done
echo "MediaWiki API not reachable"
docker compose logs --no-color > compose-logs.txt || true
exit 1
