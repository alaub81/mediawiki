#!/usr/bin/env bash
# Extensions.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# Load .env.ci without overwriting PATH
# shellcheck source=/dev/null
if [ -f .env.ci ]; then ORIG_PATH="$PATH"; set -a; . ./.env.ci; set +a; export PATH="$ORIG_PATH"; fi
: "${MW_HTTP_PORT:=8080}"
: "${E2E_EXPECT_EXTENSIONS:=$(docker compose exec -T mediawiki printenv MW_EXTRA_EXTENSIONS | tr -d '\r')}"
echo "E2E_EXPECT_EXTENSIONS: $E2E_EXPECT_EXTENSIONS"

# Normalizer: lowercase letters and digits only
norm() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]'; }

# Fetch the API response and extract every extension "name" field
JSON="$(curl -fsS "http://localhost:${MW_HTTP_PORT}/api.php?action=query&meta=siteinfo&siprop=extensions&format=json")"
API_NAMES="$(printf '%s' "$JSON" | grep -o '"name":"[^"]*"' | cut -d: -f2- | tr -d '"' )"

# Normalize the names, one per line
API_NORM=""
while IFS= read -r n; do API_NORM="${API_NORM}$(norm "$n")"$'\n'; done <<<' '"$API_NAMES"

fail=0
for ext in $E2E_EXPECT_EXTENSIONS; do
  [ -z "$ext" ] && continue
  want="$(norm "$ext")"
  if printf '%s\n' "$API_NORM" | grep -qx "$want"; then
    echo "✓ $ext"
  else
    echo "::error::Extension not loaded (by name): $ext"
    fail=1
  fi
done
exit $fail
