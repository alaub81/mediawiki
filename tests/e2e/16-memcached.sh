#!/usr/bin/env bash
# Memcached.
set -euo pipefail
docker compose exec -T mediawiki bash -lc '
  set -e
  exec 3<>/dev/tcp/memcached/11211
  printf "version\r\n" >&3
  read -r LINE <&3
  echo "$LINE" | grep -q "^VERSION" && echo "memcached OK" || { echo "$LINE"; exit 1; }
  exec 3>&- 3<&-
'
