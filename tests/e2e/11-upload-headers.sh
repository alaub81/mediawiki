#!/usr/bin/env bash
# Upload headers.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }
: "${MW_HTTP_PORT:=8080}"
BASE="http://localhost:${MW_HTTP_PORT}"
docker compose exec -T -u www-data mediawiki sh -lc 'printf test > /var/www/html/images/ci.txt'
if curl -fsSI "${BASE}/images/ci.txt" | grep -qi '^X-Content-Type-Options: *nosniff'; then
  echo "nosniff OK"
else
  echo "::error::nosniff header missing on /images/ci.txt"
  exit 1
fi
docker compose exec -T -u www-data mediawiki rm -f /var/www/html/images/ci.txt
