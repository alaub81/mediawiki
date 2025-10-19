#!/usr/bin/env bash
set -euo pipefail
cd /var/www/html

# Elasticsearch URL; in your Compose, this is usually "elasticsearch:9200"
ES_URL="${ES_URL:-http://elasticsearch:9200}"

# Get DB name: ENV or from MediaWiki itself
DBNAME="${MW_DB_NAME:-}"
if [ -z "$DBNAME" ]; then
  DBNAME="$(printf "%s\n" "echo \$wgDBname, PHP_EOL;" | php maintenance/run.php eval)" || DBNAME="wikidb"
fi

# Cirrus base name (if you overwrite it), otherwise DB name
INDEX_BASE="${MW_CIRRUS_INDEX_BASENAME:-$DBNAME}"

has_alias() { curl -fsS --max-time 4 "$ES_URL/_alias/$1" >/dev/null; }

CONTENT_ALIAS="${INDEX_BASE}_content"
GENERAL_ALIAS="${INDEX_BASE}_general"

if has_alias "$CONTENT_ALIAS" && has_alias "$GENERAL_ALIAS"; then
  echo "✓ Cirrus ready (Aliasse $CONTENT_ALIAS & $GENERAL_ALIAS vorhanden)"
else
  echo "⨯ Cirrus nicht bereit – boote Indexe neu (config + content + completion)"
  php maintenance/run.php ./extensions/CirrusSearch/maintenance/UpdateSearchIndexConfig.php --startOver
  php maintenance/run.php ./extensions/CirrusSearch/maintenance/ForceSearchIndex.php
  php maintenance/run.php ./extensions/CirrusSearch/maintenance/UpdateSearchIndexConfig.php || true
fi

# The Meta Store is now available → Update Suggester
php maintenance/run.php ./extensions/CirrusSearch/maintenance/UpdateSuggesterIndex.php
