#!/usr/bin/env bash
set -euo pipefail
cd /var/www/html

args=(maintenance/run.php ./extensions/RottenLinks/maintenance/UpdateExternalLinks.php)

# als www-data ausführen (Rechte!)
if command -v runuser >/dev/null 2>&1; then
  runuser -u www-data -- php "${args[@]}"
else
  su -s /bin/sh -c "php ${args[*]}" www-data
fi
