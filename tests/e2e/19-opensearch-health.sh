#!/usr/bin/env bash
# Opensearch health.
set -euo pipefail
set -euo pipefail
# Wait up to about 3 minutes (40 * 5s)
for _ in $(seq 1 40); do
  if docker compose exec -T opensearch sh -lc \
    "curl -fsS --max-time 4 'http://localhost:9200/_cat/health?h=status' | grep -Eq 'yellow|green'"; then
    echo "✓ OpenSearch healthy"
    exit 0
  fi
  sleep 5
done
echo "::error::OpenSearch did not become healthy (timeout)"
echo "[debug] /_cat/health:"
docker compose exec -T opensearch sh -lc "wget -qO- 'http://localhost:9200/_cat/health?v'"
echo "[debug] Plugins:"
docker compose exec -T opensearch sh -lc 'bin/opensearch-plugin list || true'
exit 1
