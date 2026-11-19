#!/usr/bin/env bash
# Sitemap freshness.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }
: "${MW_SITEMAP_IDENTIFIER:=wiki}"
p="${MW_SITEMAP_URLPATH:-}"

# Resolve the filesystem directory: "" -> /var/www/html; "sitemap/" -> /var/www/html/sitemap
norm_p="$( [ -n "$p" ] && printf '%s' "$p" | sed -E 's#^/+##; s#/+$##' || true )"
if [ -n "$norm_p" ]; then
  FS_DIR="/var/www/html/${norm_p}"
else
  FS_DIR="/var/www/html"
fi
IDX="${FS_DIR}/sitemap-index-${MW_SITEMAP_IDENTIFIER}.xml"

echo "[e2e] Expect index at: $IDX"

# Generate once if the sitemap does not exist yet
docker compose exec -T mediawiki sh -lc '
  if [ ! -s "'"$IDX"'" ] && command -v /usr/local/bin/generate-sitemap.sh >/dev/null 2>&1; then
    /usr/local/bin/generate-sitemap.sh || true
  fi
'

# Retry the check
ok=0
for _ in $(seq 1 20); do
  if docker compose exec -T mediawiki sh -lc '[ -s "'"$IDX"'" ]'; then
    age="$(docker compose exec -T mediawiki sh -lc 'now=$(date +%s); \
      mt=$(stat -c %Y "'"$IDX"'" 2>/dev/null || stat -f %m "'"$IDX"'"); echo $((now-mt))')"
    echo "sitemap age: ${age}s"
    if [ "${age:-999999}" -le 900 ]; then  # <= 15 min
      ok=1; break
    fi
  fi
  sleep 3
done

if [ "$ok" != "1" ]; then
  echo "::error::missing or stale sitemap index: $IDX"
  echo "[debug] ls target dir:"
  docker compose exec -T mediawiki sh -lc 'ls -l '"$(dirname "$IDX")"' || true'
  exit 1
fi
