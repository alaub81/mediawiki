#!/usr/bin/env bash
# Short url config.
set -euo pipefail
# Update the configuration file in the container without adding duplicate settings
docker compose exec -T -u www-data mediawiki sh -lc '
  set -eu
  f=${MW_CONFIG_FILE:-/var/www/html/LocalSettings.php}
  [ -f "$f" ] || { echo "::error::LocalSettings.php missing"; exit 1; }

  # $wgScriptPath = "";
  if grep -q "^\$wgScriptPath" "$f"; then
    sed -i '\''s#^\$wgScriptPath\s*=.*#\$wgScriptPath = "";#'\'' "$f"
  else
    # Insert before the PHP closing tag if present; otherwise append
    if grep -q "^?>" "$f"; then
      sed -i '\''s#^?>#\$wgScriptPath = "";\n?>#'\'' "$f"
    else
      printf "\n\$wgScriptPath = \"\";\n" >> "$f"
    fi
  fi

  # $wgArticlePath = "/wiki/$1";
  if grep -q "^\$wgArticlePath" "$f"; then
    sed -i '\''s#^\$wgArticlePath\s*=.*#\$wgArticlePath = "/wiki/\$1";#'\'' "$f"
  else
    if grep -q "^?>" "$f"; then
      sed -i '\''s#^?>#\$wgArticlePath = "/wiki/\$1";\n?>#'\'' "$f"
    else
      printf "\n\$wgArticlePath = \"/wiki/\\\$1\";\n" >> "$f"
    fi
  fi
'
