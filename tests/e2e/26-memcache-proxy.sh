#!/usr/bin/env bash
# Memcache proxy.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }

: "${MW_HTTP_PORT:=8080}"
: "${MEMCACHEPHP_ADMIN_USER:=admin}"
: "${MEMCACHEPHP_ADMIN_PASS:=supersecret}"
BASE="${MW_SERVER_URL:-http://localhost:${MW_HTTP_PORT}}"
base="${BASE%/}"

echo "[e2e] expect: /memcache, /mcui, /memcacheui redirect -> /memcacheui/ (301) and proxied /memcacheui/ final 200"

fail() { echo "::error::$*"; exit 1; }

get_path_from_location() {
  curl -sSI "$1" \
    | awk 'BEGIN{IGNORECASE=1} /^Location:/{print $2; exit}' \
    | tr -d '\r' \
    | sed -E 's#^[a-zA-Z][a-zA-Z0-9+.-]*://[^/]*##'
}

tries=40

# 1) /memcache -> /memcacheui/
ok=0
for _ in $(seq 1 $tries); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' -I "$base/memcache")" || true
  { [ "$code" = "301" ] || [ "$code" = "302" ]; } || { sleep 3; continue; }
  path="$(get_path_from_location "$base/memcache")"
  case "$path" in */memcacheui/) ok=1;; *) sleep 3;; esac
  [ "$ok" = 1 ] && break
done
[ "$ok" = 1 ] || fail "/memcache did not redirect to /memcacheui/"

# 2) /mcui -> /memcacheui/
ok=0
for _ in $(seq 1 $tries); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' -I "$base/mcui")" || true
  { [ "$code" = "301" ] || [ "$code" = "302" ]; } || { sleep 3; continue; }
  path="$(get_path_from_location "$base/mcui")"
  case "$path" in */memcacheui/) ok=1;; *) sleep 3;; esac
  [ "$ok" = 1 ] && break
done
[ "$ok" = 1 ] || fail "/mcui did not redirect to /memcacheui/"

# 3) /memcacheui (without trailing slash) -> /memcacheui/
ok=0
for _ in $(seq 1 $tries); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' -I "$base/memcacheui")" || true
  { [ "$code" = "301" ] || [ "$code" = "302" ]; } || { sleep 3; continue; }
  path="$(get_path_from_location "$base/memcacheui")"
  case "$path" in */memcacheui/) ok=1;; *) sleep 3;; esac
  [ "$ok" = 1 ] && break
done
[ "$ok" = 1 ] || fail "/memcacheui did not redirect to /memcacheui/"

# 4) Proxied /memcacheui/ with Basic Auth -> final 200
ok=0
for _ in $(seq 1 $tries); do
  final="$(curl -sS -o /dev/null -w '%{http_code}' -L -u "$MEMCACHEPHP_ADMIN_USER:$MEMCACHEPHP_ADMIN_PASS" \
    "$base/memcacheui/")" || true
  [ "$final" = "200" ] && { ok=1; break; }
  sleep 3
done
[ "$ok" = 1 ] || fail "proxied /memcacheui/ not returning 200 (got $final)"

# 5) Check response content without a broken pipe
html="$(curl -fsS -u "$MEMCACHEPHP_ADMIN_USER:$MEMCACHEPHP_ADMIN_PASS" "$base/memcacheui/")" || {
  echo "::error::failed to fetch /memcacheui/ content"; exit 1; }

# Match Memcache(d), phpMemcache(d)Admin, Server Stats/Slabs/Items
if printf '%s' "$html" | grep -Ei '(memcache(d)?|phpmemcache(d)?admin|server[[:space:]-]?stats|slabs|items)' >/dev/null; then
  echo "[e2e] OK"
else
  echo "::error::unexpected content at /memcacheui/"
  # Show a debug excerpt
  printf '%s\n' "$html" | head -n 80
  exit 1
fi
