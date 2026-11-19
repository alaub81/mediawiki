#!/usr/bin/env bash
# Debug details.
set -euo pipefail
docker compose exec -T -u www-data mediawiki bash -lc '
  set -e
  f="${MW_CONFIG_FILE:-/var/www/html/LocalSettings.php}"
  [ -f "$f" ] || { echo "::error::missing $f"; exit 1; }
  printf "\n# Debug (CI)\n\$wgShowExceptionDetails = true;\n" >> "$f"
'
