#!/usr/bin/env bash
set -euo pipefail
cd /var/www/html

php maintenance/run.php ./extensions/CirrusSearch/maintenance/UpdateSearchIndexConfig.php --startOver
php maintenance/run.php ./extensions/CirrusSearch/maintenance/ForceSearchIndex.php
php maintenance/run.php ./extensions/CirrusSearch/maintenance/UpdateSearchIndexConfig.php
php maintenance/run.php ./extensions/CirrusSearch/maintenance/UpdateSuggesterIndex.php
