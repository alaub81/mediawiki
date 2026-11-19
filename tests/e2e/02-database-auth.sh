#!/usr/bin/env bash
# Require the configured database login to work, rather than only checking a TCP port.
set -euo pipefail
docker compose exec -T database sh -lc '
  mariadb -h 127.0.0.1 -u root -p"${MARIADB_ROOT_PASSWORD}" -e "SELECT 1"
'
