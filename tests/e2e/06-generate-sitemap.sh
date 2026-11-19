#!/usr/bin/env bash
# Generate sitemap.
set -euo pipefail
docker compose exec -T mediawiki sh -lc '
  set -e
  /usr/local/bin/generate-sitemap.sh
'
