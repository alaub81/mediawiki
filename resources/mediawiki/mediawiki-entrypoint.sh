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

mkdir -p /usr/local/etc/php/conf.d
cat >/usr/local/etc/php/conf.d/zz-uploads.ini <<EOF
upload_max_filesize=${MW_PHP_UPLOAD_MAX_FILESIZE}
post_max_size=${MW_PHP_POST_MAX_SIZE}
EOF

# Sitemap-Ziel vorbereiten
mkdir -p "${MW_SITEMAP_FSPATH:-/var/www/html/sitemap}"
chown -R www-data:www-data "${MW_SITEMAP_FSPATH:-/var/www/html/sitemap}" || true

# Sitemap-Redirect in Apache konfigurieren (Identifier aus .env)
cat >/etc/apache2/conf-available/zz-sitemap-redirect.conf <<EOF
Redirect 301 /sitemap.xml /sitemap/sitemap-index-${MW_SITEMAP_IDENTIFIER}.xml
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
      grep -q "wfLoadExtension( 'RottenLinks' );" /var/www/html/LocalSettings.php 2>/dev/null; then
      if [ "${MW_ROTTENLINKS_RUN_ON_START:-false}" == "true" ]; then
        echo "[entrypoint] Running RottenLinks generation once on start..."
        /usr/local/bin/generate-rottenlinks.sh || echo "[entrypoint] Initial RottenLinks run failed (continuing)"
      fi
      add_cron_if_missing \
        "${MW_ROTTENLINKS_CRON:-30 */12 * * *}" \
        "/usr/local/bin/generate-rottenlinks.sh >> /proc/1/fd/1 2>&1"
    else
      echo "[entrypoint] WARN: RottenLinks not loaded – Cron skipped (set ENABLE_MW_ROTTENLINKS_CRON=1 to force)"
    fi
  else
    echo "[entrypoint] WARN: /usr/local/bin/generate-rottenlinks.sh not found – RottenLinks cron skipped"
  fi
fi

# supercronic im Hintergrund starten (loggt im JSON-Format)
# Alternative ohne JSON: /usr/local/bin/supercronic "$CRON_FILE" &
/usr/local/bin/supercronic -json "$CRON_FILE" &
echo "[entrypoint] INFO: Supercronic started with cron file $CRON_FILE"

# Apache im Vordergrund (PID 1) starten
exec "$@"
