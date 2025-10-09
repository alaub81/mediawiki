#!/usr/bin/env bash
set -euo pipefail

# Falls nur Optionen übergeben wurden, Apache-Command ergänzen
if [[ "${1:-}" == -* ]]; then
  set -- apache2-foreground "$@"
fi

# Sitemap-Ziel vorbereiten
mkdir -p "${SITEMAP_FSPATH:-/var/www/html/sitemap}"
chown -R www-data:www-data "${SITEMAP_FSPATH:-/var/www/html/sitemap}" || true

# Cronfile für supercronic erzeugen (wichtig: 5-Feld-Cronsyntax, kein "root")
CRON_FILE="/etc/cron.d/mediawiki-sitemap"
mkdir -p /etc/cron.d
# Log direkt auf Container-STDOUT/STDERR leiten
printf "%s %s\n" "${SITEMAP_CRON:-20 */12 * * *}" "/usr/local/bin/generate-sitemap.sh >> /proc/1/fd/1 2>&1" > "$CRON_FILE"

# supercronic im Hintergrund starten (loggt im JSON-Format)
# Alternative ohne JSON: /usr/local/bin/supercronic "$CRON_FILE" &
/usr/local/bin/supercronic -json "$CRON_FILE" &

# Optional: einmalig beim Start ausführen (per .env schaltbar)
if [[ "${SITEMAP_RUN_ON_START:-false}" == "true" ]]; then
  echo "[entrypoint] Running sitemap generation once on start..."
  /usr/local/bin/generate-sitemap.sh || echo "[entrypoint] Initial sitemap run failed (continuing)"
fi

# Apache im Vordergrund (PID 1) starten
exec "$@"
