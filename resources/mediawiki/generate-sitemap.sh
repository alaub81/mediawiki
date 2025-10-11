#!/usr/bin/env bash
set -euo pipefail
cd /var/www/html

server="${SITEMAP_SERVER:?SITEMAP_SERVER is required}"
fspath="${SITEMAP_FSPATH:-/var/www/html/sitemap}"
urlpath="${SITEMAP_URLPATH:-sitemap/}"

args=(maintenance/run.php generateSitemap --server "$server" --fspath "$fspath" --urlpath "$urlpath")
if [[ "${SITEMAP_SKIP_REDIRECTS:-true}" == "true" ]]; then
  args+=(--skip-redirects)
fi

mkdir -p "$fspath"
chown -R www-data:www-data "$fspath" || true

# als www-data ausführen (Rechte!)
if command -v runuser >/dev/null 2>&1; then
  runuser -u www-data -- php "${args[@]}"
else
  su -s /bin/sh -c "php ${args[*]}" www-data
fi
