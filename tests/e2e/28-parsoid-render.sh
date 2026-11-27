#!/usr/bin/env bash
# Exercise the bundled Parsoid runtime after the normal install and update.
set -euo pipefail

html=$(printf '== Parsoid smoke ==\n' | docker compose exec -T -u www-data mediawiki \
  php maintenance/run.php parse --parsoid --conf /var/www/html/conf/LocalSettings.php)
grep -Eq '<h2[^>]*>Parsoid smoke</h2>' <<< "$html"
