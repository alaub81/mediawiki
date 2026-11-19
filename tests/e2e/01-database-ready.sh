#!/usr/bin/env bash
# Database ready.
set -euo pipefail
# Wait for the database TCP port from the MediaWiki container without external tools
docker compose exec -T -u www-data mediawiki sh -lc '
  attempts=0
  until php -r \
    "exit(@fsockopen(\
      getenv(\"MW_DB_HOST\") ?: \"database\",\
      (int)(getenv(\"MW_DB_PORT\") ?: 3306),\
      \$errno, \$errstr, 2\
    ) ? 0 : 1);"; do
    attempts=$((attempts+1))
    if [ "$attempts" -ge 30 ]; then
      echo "DB TCP not reachable after 120 seconds"
      exit 1
    fi
    sleep 2
  done
  echo "DB TCP reachable"
'
