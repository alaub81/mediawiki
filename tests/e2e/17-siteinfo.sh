#!/usr/bin/env bash
# Siteinfo.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
set -Eeuo pipefail
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }
: "${MW_HTTP_PORT:=8080}"
OUT="$(curl -fsS "http://localhost:${MW_HTTP_PORT}/api.php?action=query&meta=siteinfo&format=json")"
actual_server="$(jq -r '.query.general.server // empty' <<<"$OUT")"
actual_sitename="$(jq -r '.query.general.sitename // empty' <<<"$OUT")"

if [ -z "$actual_server" ]; then
  echo "::error::no server in siteinfo"
  exit 1
fi
if [ -n "${MW_SITENAME:-}" ] && [ "$actual_sitename" != "$MW_SITENAME" ]; then
  echo "::error::unexpected sitename: expected '$MW_SITENAME', got '$actual_sitename'"
  exit 1
fi
