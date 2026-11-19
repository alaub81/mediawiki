#!/usr/bin/env bash
# Cirrus index.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
set -euo pipefail
# Load values from .env.ci if present
# shellcheck source=/dev/null
if [ -f .env.ci ]; then ORIG_PATH="$PATH"; set -a; . ./.env.ci; set +a; export PATH="$ORIG_PATH"; fi
DB="${MW_DB_NAME:-wikidb}"
for _ in $(seq 1 60); do
  if docker compose exec -T opensearch sh -lc \
    "curl -fsS 'http://localhost:9200/_cat/indices?h=index' | grep -q '${DB}_content'"; then
    echo "✓ Index ${DB}_content exists"; exit 0; fi
  sleep 3
done
echo "::error::Cirrus content index not found"; exit 1
