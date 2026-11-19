#!/usr/bin/env bash
# Create page.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# Load .env.ci without overwriting PATH
# shellcheck source=/dev/null
if [ -f .env.ci ]; then ORIG_PATH="$PATH"; set -a; . ./.env.ci; set +a; export PATH="$ORIG_PATH"; fi
: "${E2E_PAGE_TITLE:=E2E-Tagcloud-Test}"
: "${E2E_MARK:=E2E_TAGCLOUD_OK}"
: "${E2E_SEARCH_MARK:=CirrusE2EQuasar92741}"
: "${E2E_BAD_URL:=http://does-not-exist.invalid/e2e-broken}"

docker compose exec -T -u www-data mediawiki bash -lc '
  set -e
  cat >/tmp/e2e-page.txt <<EOF
== E2E ==
Marker: '"$E2E_MARK"'
Search marker: '"$E2E_SEARCH_MARK"'

<tagcloud></tagcloud>

Broken link: ['"$E2E_BAD_URL"' E2E-Broken-Link]
EOF
# Create or overwrite the page through maintenance, without logging in
php maintenance/run.php edit --summary "e2e create" --no-rc "'"$E2E_PAGE_TITLE"'" < /tmp/e2e-page.txt
'
