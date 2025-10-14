#!/usr/bin/env bash
set -euo pipefail
cd /var/www/html

server="${MW_SITEMAP_SERVER:?MW_SITEMAP_SERVER is required}"
fspath="${MW_SITEMAP_FSPATH:-/var/www/html/sitemap}"
urlpath="${MW_SITEMAP_URLPATH:-sitemap/}"
identifier="${MW_SITEMAP_IDENTIFIER:-wiki}"

args=(maintenance/run.php generateSitemap --identifier "$identifier" --server "$server" --fspath "$fspath" --urlpath "$urlpath")
if [[ "${MW_SITEMAP_SKIP_REDIRECTS:-true}" == "true" ]]; then
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
