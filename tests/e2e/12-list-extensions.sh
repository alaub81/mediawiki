#!/usr/bin/env bash
# List extensions.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }
: "${MW_HTTP_PORT:=8080}"
: "${E2E_EXPECT_EXTENSIONS:=}"   # empty means list extensions only
JSON="$(curl -fsS "http://localhost:${MW_HTTP_PORT}/api.php?action=query&meta=siteinfo&siprop=extensions&format=json")"
if [ -z "$E2E_EXPECT_EXTENSIONS" ]; then
  echo "$JSON" | grep -o '"name":"[^"]*"' | sed 's/.*:"//;s/"$//' | sort -u | sed 's/^/ - /'
  exit 0
fi
fail=0
for ext in $E2E_EXPECT_EXTENSIONS; do
  if echo "$JSON" | grep -q "\"name\":\"$ext\""; then
    echo "✓ $ext"
  else
    echo "::error::Extension not loaded: $ext"
    fail=1
  fi
done
exit $fail
