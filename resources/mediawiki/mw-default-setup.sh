#!/usr/bin/env bash
set -eu

: "${MW_CONFIG_FILE:=/var/www/html/LocalSettings.php}"
MW_CONFIG_FILE_PATH=$(dirname "$MW_CONFIG_FILE" 2>/dev/null || echo "/var/www/html")
if [ -n "${MW_CONFIG_FILE_PATH:-}" ]; then
  if [ ! -d "$MW_CONFIG_FILE_PATH" ]; then
    mkdir -p -- "$MW_CONFIG_FILE_PATH"
  fi
fi

cd /var/www/html
run="php maintenance/run.php"

# Hilfetext einmal ermitteln
INSTALL_HELP="$($run install --help 2>&1 || true)"

# Welche Flags unterstützt der Installer?
HAS_EXT=0; HAS_WITH=0
printf '%s' "$INSTALL_HELP" | grep -q -- '--extensions'       && HAS_EXT=1
printf '%s' "$INSTALL_HELP" | grep -q -- '--with-extensions'  && HAS_WITH=1

# Space → CSV aus MW_ACTIVE_EXTENSIONS
EXT_CSV=""
if [ -n "${MW_ACTIVE_EXTENSIONS:-}" ]; then
  set -f  # kein Globbing
  for e in $MW_ACTIVE_EXTENSIONS; do
    if [ -z "$EXT_CSV" ]; then EXT_CSV="$e"; else EXT_CSV="$EXT_CSV,$e"; fi
  done
  set +f
fi

# Welches Flag nutzen?
EXT_FLAG=""
if [ -z "$EXT_CSV" ]; then
  if [ $HAS_WITH -eq 1 ]; then
    EXT_FLAG="--with-extensions"
  else
    echo "[install] Hinweis: --with-extensions nicht verfügbar; keine Extensions per Installer geladen." >&2
  fi
else
  if [ $HAS_EXT -eq 1 ]; then
    EXT_FLAG="--extensions $EXT_CSV"
  elif [ $HAS_WITH -eq 1 ]; then
    echo "[install] Hinweis: --extensions fehlt; benutze --with-extensions und ignoriere Liste." >&2
    EXT_FLAG="--with-extensions"
  else
    echo "[install] Hinweis: Weder --extensions noch --with-extensions verfügbar; lade Extensions nachträglich." >&2
  fi
fi

if [ -f "${MW_CONFIG_FILE:-/var/www/html/LocalSettings.php}" ]; then
  echo "${MW_CONFIG_FILE} exists → running update.php"
  $run update
else
  echo "No ${MW_CONFIG_FILE} → running install.php"

  # DB-Port erreichbar? (failsafe zusätzlich zum vorherigen DB-Wait)
  end=$((SECONDS+120))
  until php -r "exit(@fsockopen(getenv(\"MW_DB_HOST\")?: \"database\", (int)(getenv(\"MW_DB_PORT\")?:3306))?0:1);"; do
    [ $SECONDS -ge $end ] && { echo "DB not reachable"; exit 1; }
    sleep 2
  done
  echo ${EXT_FLAG:+$EXT_FLAG}
  # Installation
  $run install \
    --confpath "${MW_CONFIG_FILE_PATH}" \
    --dbtype mysql \
    --dbserver  "${MW_DB_HOST:-database}:${MW_DB_PORT:-3306}" \
    --dbname    "${MW_DB_NAME:-wikidb}" \
    --dbuser    "${MW_DB_USER:-wikiuser}" \
    --dbpass    "${MW_DB_PASS:-w1k1pass}" \
    --installdbuser "${MW_DB_ADMIN_USER:-root}" \
    --installdbpass "${MARIADB_ROOT_PASSWORD:-ciRootPassw0rd}" \
    --lang      "${MW_LANG:-de}" \
    --server    "http://localhost:${MW_HTTP_PORT:-8080}" \
    --scriptpath "" \
    --pass      "${MW_ADMIN_PASS:-AdminPass123}" \
    ${EXT_FLAG:+$EXT_FLAG} \
    "${MW_SITENAME:-Wiki CI}" \
    "${MW_ADMIN_USER:-Admin}"
fi
echo "[install] Installation/Update done."

# --- $wgScriptPath und $wgArticlePath in LocalSettings.php setzen ---
# Datei
f="${MW_CONFIG_FILE:-/var/www/html/LocalSettings.php}"
  [ -f "$f" ] || { echo "Config file $f not found"; exit 1; }

# $wgScriptPath = "";
if grep -q "^\$wgScriptPath" "$f"; then
  sed -i "s#^\$wgScriptPath[[:space:]]*=.*#\$wgScriptPath = \"\";#" "$f"
else
  if grep -q '^?>' "$f"; then
    sed -i "s#^?>#\$wgScriptPath = \"\";\\n?>#" "$f"
  else
    printf "\n\$wgScriptPath = "";\n" >> "$f"
  fi
fi

# $wgArticlePath = "/wiki/$1";
if grep -q "^\$wgArticlePath" "$f"; then
  sed -i "s#^\$wgArticlePath[[:space:]]*=.*#\$wgArticlePath = \"/wiki/\\\$1\";#" "$f"
else
  if grep -q '^?>' "$f"; then
    sed -i "s#^?>#\$wgArticlePath = \"/wiki/\\\$1\";\\n?>#" "$f"
  else
    printf "\n\$wgArticlePath = \"/wiki/\$1\";\n" >> "$f"
  fi
fi

# --- Elastica/Cirrus sicher laden (nur falls noch nicht vorhanden) ---
if ! grep -Fq "wfLoadExtension( 'Elastica' );" "$f"; then
  printf "%s\n" "wfLoadExtension( 'Elastica' );" >> "$f"
fi
if ! grep -Fq "wfLoadExtension( 'CirrusSearch' );" "$f"; then
  printf "%s\n" "wfLoadExtension( 'CirrusSearch' );" >> "$f"
fi

# --- Cirrus-Block idempotent schreiben ---
cat >>"$f" <<'PHP'
# --- CirrusSearch settings (auto) BEGIN ---
wfLoadExtension( 'Elastica' );
wfLoadExtension( 'CirrusSearch' );

$wgSearchType = 'CirrusSearch';
$wgCirrusSearchServers = [ 'elasticsearch' ];
$wgCirrusSearchUseCompletionSuggester = true;

$wgRelatedArticlesDescriptionSource = 'pagedescription';
$wgRelatedArticlesUseCirrusSearchApiUrl = '/api.php';
$wgRelatedArticlesUseCirrusSearch = true;
# --- CirrusSearch settings (auto) END ---
PHP

echo "[cirrus] CirrusSearch-Konfiguration wurde in $f aktualisiert."
