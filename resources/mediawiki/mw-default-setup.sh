#!/usr/bin/env bash
set -eu

cd /var/www/html
run="php maintenance/run.php"

# Space → CSV (komma-getrennt), robust & POSIX
EXT_CSV=""
if [ -n "${MW_EXTENSIONS:-}" ]; then
  for e in $MW_EXTENSIONS; do
    [ -z "$EXT_CSV" ] && EXT_CSV="$e" || EXT_CSV="$EXT_CSV,$e"
  done
fi

# --extensions nur nutzen, wenn unterstützt
EXT_FLAG=""
if $run install --help 2>&1 | grep -q -- '--extensions'; then
  [ -n "$EXT_CSV" ] && EXT_FLAG="--extensions $EXT_CSV"
fi

if [ -f LocalSettings.php ]; then
  echo "[e2e] LocalSettings.php exists → running update.php"
  $run update --quick --no-interactive
else
  echo "[e2e] No LocalSettings.php → running install.php"

  # DB-Port erreichbar? (failsafe zusätzlich zum vorherigen DB-Wait)
  end=$((SECONDS+120))
  until php -r "exit(@fsockopen(getenv(\"MW_DB_HOST\")?: \"database\", (int)(getenv(\"MW_DB_PORT\")?:3306))?0:1);"; do
    [ $SECONDS -ge $end ] && { echo "DB not reachable"; exit 1; }
    sleep 2
  done

  # Installation
  $run install \
    --confpath /var/www/html \
    --dbtype mysql \
    --dbserver  "${MW_DB_HOST:-database}:${MW_DB_PORT:-3306}" \
    --dbname    "${MW_DB_NAME:-wikidb}" \
    --dbuser    "${MW_DB_USER:-wikiuser}" \
    --dbpass    "${MW_DB_PASS:-w1k1pass}" \
    --installdbuser "${MW_DB_ADMIN_USER:-root}" \
    --installdbpass "${MARIADB_ROOT_PASSWORD:-ciRootPassw0rd}" \
    --lang      "${MW_LANG:-de}" \
    --server    http://localhost:${MW_HTTP_PORT:-8080} \
    --scriptpath "" \
    --pass      "${MW_ADMIN_PASS:-AdminPass123}" \
    ${EXT_FLAG:+$EXT_FLAG} \
    "${MW_SITENAME:-Wiki CI}" \
    "${MW_ADMIN_USER:-Admin}"
fi

# --- $wgScriptPath und $wgArticlePath in LocalSettings.php setzen ---
f=/var/www/html/LocalSettings.php
[ -f "$f" ] || { echo "::error::LocalSettings.php missing"; exit 1; }

# $wgScriptPath = "";
if grep -q "^\$wgScriptPath" "$f"; then
  sed -i 's#^\$wgScriptPath\s*=.*#\$wgScriptPath = "";#' "$f"
else
  # vor dem PHP-Schluss einfügen, falls vorhanden – sonst ans Ende
  if grep -q "^?>" "$f"; then
    sed -i 's#^?>#\$wgScriptPath = "";\n?>#' "$f"
  else
    printf "\n\$wgScriptPath = \"\";\n" >> "$f"
  fi
fi

# $wgArticlePath = "/wiki/$1";
if grep -q "^\$wgArticlePath" "$f"; then
  sed -i 's#^\$wgArticlePath\s*=.*#\$wgArticlePath = "/wiki/\$1";#' "$f"
else
  if grep -q "^?>" "$f"; then
    sed -i 's#^?>#\$wgArticlePath = "/wiki/\$1";\n?>#' "$f"
  else
    printf "\n\$wgArticlePath = \"/wiki/\\\$1\";\n" >> "$f"
  fi
fi
