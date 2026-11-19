#!/usr/bin/env bash
# Install wiki.
set -euo pipefail
docker compose exec -T -u www-data mediawiki sh -lc '
  /usr/local/bin/mw-default-setup.sh
'
