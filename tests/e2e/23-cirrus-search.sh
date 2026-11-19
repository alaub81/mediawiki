#!/usr/bin/env bash
# Cirrus search.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
set -Eeuo pipefail
# shellcheck source=/dev/null
if [ -f .env.ci ]; then ORIG_PATH="$PATH"; set -a; . ./.env.ci; set +a; export PATH="$ORIG_PATH"; fi
: "${MW_HTTP_PORT:=8080}"
: "${E2E_PAGE_TITLE:=E2E-Tagcloud-Test}"
: "${E2E_SEARCH_MARK:=CirrusE2EQuasar92741}"
API="http://localhost:${MW_HTTP_PORT}/api.php"

for _ in $(seq 1 30); do
  result="$(curl -fsS --get "$API" \
    --data-urlencode 'action=query' \
    --data-urlencode 'list=search' \
    --data-urlencode "srsearch=${E2E_SEARCH_MARK}" \
    --data-urlencode 'srlimit=10' \
    --data-urlencode 'format=json')"
  if jq -e --arg title "$E2E_PAGE_TITLE" \
      '.query.search | any(.title == $title)' <<<"$result" >/dev/null; then
    echo "✓ CirrusSearch found '$E2E_PAGE_TITLE' by its unique marker"
    exit 0
  fi
  sleep 2
done

echo "::error::CirrusSearch did not find '$E2E_PAGE_TITLE' by marker '$E2E_SEARCH_MARK'"
jq '.' <<<"${result:-{}}" || true
exit 1
