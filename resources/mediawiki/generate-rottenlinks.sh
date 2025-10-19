#!/usr/bin/env bash
set -euo pipefail
cd /var/www/html

args=(maintenance/run.php ./extensions/RottenLinks/maintenance/UpdateExternalLinks.php)

# Run as www-data (rights!)
if command -v runuser >/dev/null 2>&1; then
  runuser -u www-data -- php "${args[@]}"
else
  su -s /bin/sh -c "php ${args[*]}" www-data
fi
