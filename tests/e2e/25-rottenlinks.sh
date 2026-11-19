#!/usr/bin/env bash
# Rottenlinks.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
set -Eeuo pipefail
# shellcheck source=/dev/null
[ -f .env.ci ] && { P="$PATH"; set -a; . ./.env.ci; set +a; PATH="$P"; }

: "${MW_HTTP_PORT:=8080}"
: "${MW_SERVER_URL:=http://localhost:${MW_HTTP_PORT}}"
: "${E2E_BAD_URL:=http://does-not-exist.invalid/e2e-broken}"

# 1) Start generation with the script, or run jobs as a fallback
if docker compose exec -T mediawiki test -x /usr/local/bin/generate-rottenlinks.sh; then
  docker compose exec -T mediawiki /usr/local/bin/generate-rottenlinks.sh || true
else
  docker compose exec -T -u www-data mediawiki php maintenance/run.php runJobs --maxjobs=200 || true
fi

# 2) Poll the RottenLinks special page and look for the URL
base="${MW_SERVER_URL%/}"
rl_url="$base/wiki/Spezial:RottenLinks"
ok=0
for _ in $(seq 1 10); do
  body="$(curl -fsSL "$rl_url" || true)"
  if printf '%s' "$body" | grep -Fq "$E2E_BAD_URL"; then
    echo "[e2e] OK — RottenLinks lists $E2E_BAD_URL"
    ok=1; break
  fi
  sleep 3
done
if [ "$ok" != "1" ]; then
  echo "::error::Broken URL not found on Spezial:RottenLinks"
  echo "[debug] first 120 lines:"; printf '%s' "${body:-}" | sed -n '1,120p'
  exit 1
fi
