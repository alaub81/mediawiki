#!/bin/sh
# MediaWiki Sitemap generation script
set -eu

# Defaults
: "${MW_ROOT:=/var/www/html}"
: "${MW_SITEMAP_IDENTIFIER:=wiki}"

RUN_PHP="$MW_ROOT/maintenance/run.php"
SCRIPT="generateSitemap"

is_true() { case "${1:-}" in 1|true|TRUE|yes|YES|on|ON) return 0;; *) return 1;; esac; }

# Build args dynamically (only set if ENV is not empty)
set --

[ -n "${MW_CONFIG_FILE:-}" ]       && set -- "$@" --conf "$MW_CONFIG_FILE"
[ -n "${MW_SITEMAP_SERVER:-}" ]    && set -- "$@" --server "$MW_SITEMAP_SERVER"
[ -n "${MW_SITEMAP_URLPATH:-}" ]   && set -- "$@" --urlpath "$MW_SITEMAP_URLPATH"
[ -n "${MW_SITEMAP_IDENTIFIER:-}" ]&& set -- "$@" --identifier "$MW_SITEMAP_IDENTIFIER"
is_true "${MW_SITEMAP_SKIP_REDIRECTS:-}" && set -- "$@" --skip-redirects

# --fspath ONLY if MW_SITEMAP_URLPATH ≠ empty → Subfolders of MW_ROOT
_clean_seg() { printf '%s' "$1" | sed -E 's#^/+##; s#/+$##'; }
if [ -n "${MW_SITEMAP_URLPATH:-}" ]; then
  seg="$(_clean_seg "$MW_SITEMAP_URLPATH")"
  if [ -n "$seg" ]; then
    fspath="$MW_ROOT/$seg"
    mkdir -p -- "$fspath"
    chown -R www-data:www-data "$fspath" || true
    set -- "$@" --fspath "$fspath"
  fi
fi

# Run as www-data
if command -v runuser >/dev/null 2>&1; then
  exec runuser -u www-data -- php "$RUN_PHP" "$SCRIPT" "$@"
else
  # Fallback su (secure quote)
  shell_quote() { printf "%s" "$1" | sed "s/'/'\"'\"'/g; s/.*/'&'/"; }
  cmd="php $(shell_quote "$RUN_PHP") $(shell_quote "$SCRIPT")"
  for a in "$@"; do cmd="$cmd $(shell_quote "$a")"; done
  exec su -s /bin/sh -c "$cmd" www-data
fi
