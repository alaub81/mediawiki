#!/usr/bin/env bash
# Cirrus bootstrap.
set -euo pipefail
set -euo pipefail
docker compose exec -T mediawiki sh -lc '
  /usr/local/bin/generate-opensearch-index.sh
'
