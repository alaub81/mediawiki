#!/usr/bin/env bash
# Homepage.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
set -Eeuo pipefail

# Load environment values if available
# shellcheck source=/dev/null
[ -f .env.ci ] && { P="$PATH"; set -a; . ./.env.ci; set +a; PATH="$P"; }

: "${MW_HTTP_PORT:=8080}"
: "${MW_SERVER_URL:=http://localhost:${MW_HTTP_PORT}}"
: "${E2E_PAGE_TITLE:=E2E-Tagcloud-Test}"
: "${E2E_MARK:=E2E_TAGCLOUD_OK}"

url="${MW_SERVER_URL%/}/wiki/${E2E_PAGE_TITLE// /_%20}"
echo "[e2e] GET $url"

tmpdir="$(mktemp -d)"
code="$(curl -sS --fail-with-body -L -D "$tmpdir/headers" -o "$tmpdir/body" -w '%{http_code}' "$url" || true)"
echo "[e2e] HTTP $code"

# 1) Catch HTTP error codes
if [ -z "${code:-}" ] || [ "$code" -ge 500 ]; then
  echo "::error::Server error (HTTP $code)"
  sed -n '1,80p' "$tmpdir/headers" || true
  tail -n 120 "$tmpdir/body" || true
  docker compose logs --no-color --tail 200 mediawiki || true
  exit 1
fi

# 2) Detect exception markers in the body, including HTTP 200 responses
if grep -qiE 'MediaWiki internal error|Original exception|Fatal error|Backtrace' "$tmpdir/body"; then
  echo "::error::Exception markers found in response body"
  sed -n '1,80p' "$tmpdir/headers" || true
  # Show a body excerpt around the first match
  line="$(grep -niE 'MediaWiki internal error|Original exception|Fatal error|Backtrace' "$tmpdir/body" | \
    head -n1 | cut -d: -f1 || true)"
  if [ -n "$line" ]; then
    start=$(( line>40 ? line-40 : 1 )); end=$(( line+120 ))
    sed -n "${start},${end}p" "$tmpdir/body" || true
  else
    tail -n 120 "$tmpdir/body" || true
  fi
  docker compose logs --no-color --tail 200 mediawiki || true
  exit 1
fi

# 3) Check for expected text as a simple smoke test
if ! grep -qi -- "$E2E_MARK" "$tmpdir/body"; then
  echo "::error::Expected text not found: $E2E_MARK"
  sed -n '1,60p' "$tmpdir/headers" || true
  head -n 120 "$tmpdir/body" || true
  exit 1
fi

echo "[e2e] OK — homepage renders and contains: $E2E_MARK"
