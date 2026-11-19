#!/usr/bin/env bash
# Short urls.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }
: "${MW_HTTP_PORT:=8080}"
BASE="http://localhost:${MW_HTTP_PORT}"
for _ in $(seq 1 30); do
  H="$(curl -fsSI "${BASE}/index.php/Special:Version" || true)"
  echo "$H" | grep -qiE '^HTTP/.* 301 ' || { sleep 2; continue; }
  echo "$H" | grep -qiE '^Location: .*/wiki/(Special|Spezial):Version\s*$' && { echo "Short URLs OK"; exit 0; }
  sleep 2
done
echo "::error::Short URL redirect failed"
curl -v -sI "${BASE}/index.php/Special:Version" || true
exit 1
