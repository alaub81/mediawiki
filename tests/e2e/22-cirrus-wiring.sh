#!/usr/bin/env bash
# Cirrus wiring.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
set -euo pipefail
# Load .env.ci without overwriting PATH
# shellcheck source=/dev/null
if [ -f .env.ci ]; then ORIG_PATH="$PATH"; set -a; . ./.env.ci; set +a; export PATH="$ORIG_PATH"; fi
: "${MW_HTTP_PORT:=8080}"
BASE="http://localhost:${MW_HTTP_PORT}"

# 1) Is CirrusSearch the active backend?
BACKEND="$(docker compose exec -T mediawiki sh -lc 'printf "%s\n" "echo \$wgSearchType, PHP_EOL;" \
  | php maintenance/run.php eval')"
if [ "$BACKEND" != "CirrusSearch" ]; then
  echo "::error::wgSearchType is '$BACKEND'; expected 'CirrusSearch'"
  exit 1
fi
echo "✓ wgSearchType=CirrusSearch"

# 2) Is the CirrusSearch API reachable?
if ! curl -fsS "${BASE}/api.php?action=cirrus-config-dump&format=json" >/dev/null; then
  echo "::error::cirrus-config-dump is unreachable"
  exit 1
fi
echo "✓ cirrus-config-dump is reachable"

# 3) Optional morelike smoke test; failure is not critical
if curl -fsS "${BASE}/api.php?action=query&list=search&srsearch=morelike:Hauptseite&srlimit=3&format=json" \
    | grep -q '"search":\[' ; then
  echo "✓ morelike returns JSON"
else
  echo "::warning::morelike returned no matches (index may still be building); this is diagnostic only"
fi
