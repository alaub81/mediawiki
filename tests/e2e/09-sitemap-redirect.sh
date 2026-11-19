#!/usr/bin/env bash
# Sitemap redirect.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# Load environment values without overwriting PATH
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }

: "${MW_HTTP_PORT:=8080}"
BASE="${MW_SERVER_URL:-http://localhost:${MW_HTTP_PORT}}"

echo "[e2e] Expect: ${BASE}/sitemap.xml redirects (301) and final target returns 200"

ok=0
for _ in $(seq 1 40); do
  # 1) Is the MediaWiki API reachable?
  if ! curl -fsS "${BASE%/}/api.php?action=query&meta=siteinfo&format=json" | grep -q '"query"'; then
    sleep 3; continue
  fi

  # 2) Check only the first /sitemap.xml response status (without -L)
  first_code="$(curl -sS -o /dev/null -w '%{http_code}' -I "${BASE%/}/sitemap.xml" || echo)"
  # Default: 301. To accept 302 as well, replace the next line with:
  # [ "$first_code" = "301" ] || [ "$first_code" = "302" ]
  [ "$first_code" = "301" ] || { sleep 3; continue; }

  # 3) Check the final status after following redirects (with -L)
  final_code="$(curl -sS -o /dev/null -w '%{http_code}' -IL "${BASE%/}/sitemap.xml" || echo)"
  if [ "$final_code" = "200" ]; then
    echo "[e2e] OK: first=$first_code, final=$final_code"
    ok=1
    break
  fi
  sleep 3
done

if [ "$ok" != "1" ]; then
  echo "::error::Sitemap redirect/target check failed"
  echo "[debug] HEAD /sitemap.xml (no follow):"
  curl -v -sI "${BASE%/}/sitemap.xml" || true
  echo "[debug] HEAD /sitemap.xml (follow -L):"
  curl -v -sIL "${BASE%/}/sitemap.xml" || true
  echo "[debug] MW api siteinfo:"
  curl -sS "${BASE%/}/api.php?action=query&meta=siteinfo&format=json" | head -c 400 || true
  exit 1
fi
