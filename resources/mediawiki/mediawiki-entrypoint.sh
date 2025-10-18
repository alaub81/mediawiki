#!/usr/bin/env bash
set -euo pipefail

# Falls nur Optionen übergeben wurden, Apache-Command ergänzen
if [[ "${1:-}" == -* ]]; then
  set -- apache2-foreground "$@"
fi

# PHP-Uploadgrößen setzen (per .env änderbar)
: "${MW_PHP_UPLOAD_MAX_FILESIZE:=100M}"
: "${MW_PHP_POST_MAX_SIZE:=100M}"
: "${MW_SITEMAP_IDENTIFIER:-wiki}"
MW_CONFIG_FILE="${MW_CONFIG_FILE:-/var/www/html/LocalSettings.php}"

mkdir -p /usr/local/etc/php/conf.d
cat >/usr/local/etc/php/conf.d/zz-uploads.ini <<EOF
upload_max_filesize=${MW_PHP_UPLOAD_MAX_FILESIZE}
post_max_size=${MW_PHP_POST_MAX_SIZE}
EOF

# Sitemap-Ziel vorbereiten
# mkdir -p "${MW_SITEMAP_FSPATH:-/var/www/html/sitemap}"
# chown -R www-data:www-data "${MW_SITEMAP_FSPATH:-/var/www/html/sitemap}" || true

# Sitemap-Redirect in Apache konfigurieren (Identifier aus .env)
# cat >/etc/apache2/conf-available/zz-sitemap-redirect.conf <<EOF
# Redirect 301 /sitemap.xml /sitemap/sitemap-index-${MW_SITEMAP_IDENTIFIER}.xml
# EOF
# a2enconf -q zz-sitemap-redirect || true
# --- Sitemap-Redirect in Apache aus ENV bauen ---
ident="${MW_SITEMAP_IDENTIFIER:-wiki}"

# Prefix nur verwenden, wenn gesetzt; auf "/foo/" normalisieren
p="${MW_SITEMAP_URLPATH:-}"
if [ -n "$p" ]; then
  case "$p" in /*) ;; *) p="/$p";; esac
  case "$p" in */) ;; *) p="$p/";; esac
  prefix="$p"
else
  prefix="/"   # <— wenn leer: führenden Slash sicherstellen
fi

target="${prefix}sitemap-index-${ident}.xml"

cat >/etc/apache2/conf-available/zz-sitemap-redirect.conf <<EOF
Redirect 301 /sitemap.xml $target
EOF
a2enconf -q zz-sitemap-redirect || true

# --- Cronfile vorbereiten ---
CRON_FILE="/etc/cron.d/mediawiki"
mkdir -p "$(dirname "$CRON_FILE")"
# Bei jedem Start neu schreiben (klarer als anhängen)
: > "$CRON_FILE"

# Helper: Zeile nur einfügen, wenn noch nicht vorhanden
add_cron_if_missing() {
  local spec="$1" cmd="$2"
  grep -Fq -- "$cmd" "$CRON_FILE" 2>/dev/null || printf "%s %s\n" "$spec" "$cmd" >> "$CRON_FILE"
}

# MediaWiki Update
if [ "${MW_AUTO_UPDATE:-false}" = "true" ] && [ -f "${MW_CONFIG_FILE:-/var/www/html/LocalSettings.php}" ]; then
  echo "[entrypoint] running database update (idempotent)…"
  # Gegen parallele Starts absichern:
  mkdir -p /run; exec 9>/run/mw-update.lock
  if flock -n 9; then
    php maintenance/run.php update --quick --skip-config-validation || {
      echo "::error::update.php failed"; exit 1; }
  else
    echo "[entrypoint] another update is in progress; skipping"
  fi
fi

# --- Sitemap-Job (nur wenn Skript existiert) ---
if [ "${MW_SITEMAP_GENERATION:-}" != "true" ]; then
  echo "[entrypoint] INFO: MW_SITEMAP_GENERATION not set to 'true' – sitemap cron skipped"
else
  if [ "${MW_SITEMAP_RUN_ON_START:-false}" == "true" ]; then
    echo "[entrypoint] Running sitemap generation once on start..."
    /usr/local/bin/generate-sitemap.sh || echo "[entrypoint] Initial sitemap run failed (continuing)"
  fi
  if [ -x /usr/local/bin/generate-sitemap.sh ]; then
    add_cron_if_missing \
      "${MW_SITEMAP_CRON:-20 */12 * * *}" \
      "/usr/local/bin/generate-sitemap.sh >> /proc/1/fd/1 2>&1"
  else
    echo "[entrypoint] WARN: /usr/local/bin/generate-sitemap.sh not found – sitemap cron skipped"
  fi
fi

# --- RottenLinks-Job (existiert Skript? Extension vorhanden?) ---
if [ "${MW_ROTTENLINKS_GENERATION:-}" != "true" ]; then
  echo "[entrypoint] INFO: MW_ROTTENLINKS_GENERATION not set to 'true' – RottenLinks cron skipped"
else
  # 1) Skript vorhanden?
  if [ -x /usr/local/bin/generate-rottenlinks.sh ]; then
    # 2) Extension vorhanden? (mindestens eines der Kriterien)
    if [ -d /var/www/html/extensions/RottenLinks ] || \
      grep -q "wfLoadExtension( 'RottenLinks' );" "${MW_CONFIG_FILE}" 2>/dev/null; then
      if [ "${MW_ROTTENLINKS_RUN_ON_START:-false}" == "true" ]; then
        echo "[entrypoint] Running RottenLinks generation once on start..."
        /usr/local/bin/generate-rottenlinks.sh || echo "[entrypoint] Initial RottenLinks run failed (continuing)"
      fi
      add_cron_if_missing \
        "${MW_ROTTENLINKS_CRON:-30 */12 * * *}" \
        "/usr/local/bin/generate-rottenlinks.sh >> /proc/1/fd/1 2>&1"
    else
      echo "[entrypoint] WARN: RottenLinks not loaded – Cron skipped"
    fi
  else
    echo "[entrypoint] WARN: /usr/local/bin/generate-rottenlinks.sh not found – RottenLinks cron skipped"
  fi
fi

# --- CirrusSearchIndex-Job (existiert Skript? Extension vorhanden?) ---
if [ "${MW_CS_INDEX_UPDATE:-}" != "true" ]; then
  echo "[entrypoint] INFO: MW_CS_INDEX_UPDATE not set to 'true' – CirrusSearch index cron skipped"
else
  # 1) Skript vorhanden?
  if [ -x /usr/local/bin/update-cirrussearch-index.sh ]; then
    # 2) Extension vorhanden? (mindestens eines der Kriterien)
    if [ -d /var/www/html/extensions/CirrusSearch ] || \
      grep -q "wfLoadExtension( 'CirrusSearch' );" "${MW_CONFIG_FILE}" 2>/dev/null; then
      if [ "${MW_CS_INDEX_RUN_ON_START:-false}" == "true" ]; then
        echo "[entrypoint] Running CirrusSearch generation once on start..."
        /usr/local/bin/update-cirrussearch-index.sh || echo "[entrypoint] Initial CirrusSearch index run failed (continuing)"
      fi
      add_cron_if_missing \
        "${MW_CS_INDEX_CRON:-15 * * * *}" \
        "/usr/local/bin/update-cirrussearch-index.sh >> /proc/1/fd/1 2>&1"
    else
      echo "[entrypoint] WARN: CirrusSearch not loaded – Cron skipped"
    fi
  else
    echo "[entrypoint] WARN: /usr/local/bin/update-cirrussearch-index.sh not found – CirrusSearch index cron skipped"
  fi
fi

if [ "${MW_JOBS_CRON:-false}" = "true" ]; then
  add_cron_if_missing \
    "* * * * *" \
    "php /var/www/html/maintenance/run.php runJobs --wait --maxjobs=200"
fi

# supercronic im Hintergrund starten (loggt im JSON-Format)
# Alternative ohne JSON: /usr/local/bin/supercronic "$CRON_FILE" &
/usr/local/bin/supercronic -json "$CRON_FILE" &
echo "[entrypoint] INFO: Supercronic started with cron file $CRON_FILE"

# Apache im Vordergrund (PID 1) starten
exec "$@"
