#!/usr/bin/env bash
# Antivirus upload.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
set -Eeuo pipefail
# Read .env if present
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }
# jq is a checked prerequisite of the shared E2E runner.

# Base URL + API
: "${MW_HTTP_PORT:=8080}"
BASE="http://localhost:${MW_HTTP_PORT}"
MW_API="$BASE/api.php"

if [ "${CLAMAV_ENABLED:-}" != "true" ]; then
  echo "::error::CLAMAV_ENABLED must be true for the antivirus E2E test"
  exit 1
fi
container_clamav_enabled="$(docker compose exec -T mediawiki printenv CLAMAV_ENABLED 2>/dev/null | tr -d '\r' || true)"
if [ "$container_clamav_enabled" != "true" ]; then
  echo "::error::MediaWiki container has CLAMAV_ENABLED=$container_clamav_enabled"
  exit 1
fi

# Wait until clamd in the sidecar answers PONG (remote scanner must be ready)
clamav_ready=0
for _ in $(seq 1 60); do
  if docker compose exec -T mediawiki sh -lc 'echo PING | nc -w 2 clamav 3310 | grep -q PONG'; then
    echo "clamd ready"
    clamav_ready=1
    break
  fi
  sleep 2
done
if [ "$clamav_ready" -ne 1 ]; then
  echo "::error::clamd did not become ready after 120 seconds"
  exit 1
fi

# Prepare cookie jar
COOKIE="$(mktemp)"
trap 'rm -f "$COOKIE"' EXIT

# 1) Get login token
LOGIN_TOKEN="$(
  curl -sS -c "$COOKIE" -b "$COOKIE" -X POST "$MW_API" \
    -H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8' \
    --data 'action=query&meta=tokens&type=login&format=json' \
  | jq -r '.query.tokens.logintoken'
)"
test -n "$LOGIN_TOKEN" && test "$LOGIN_TOKEN" != "null"

# 2) Login using the admin from .env.ci (created by your setup)
: "${MW_ADMIN_USER:?MW_ADMIN_USER missing}"
: "${MW_ADMIN_PASS:?MW_ADMIN_PASS missing}"
LOGIN_JSON="$(
  curl -sS -c "$COOKIE" -b "$COOKIE" -X POST "$MW_API" \
    -H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8' \
    --data-urlencode "action=login" \
    --data-urlencode "lgname=${MW_ADMIN_USER}" \
    --data-urlencode "lgpassword=${MW_ADMIN_PASS}" \
    --data-urlencode "lgtoken=${LOGIN_TOKEN}" \
    --data-urlencode "format=json"
)"
test "$(jq -r '.login.result' <<<"$LOGIN_JSON")" = "Success"

# 3) Get CSRF token
CSRF="$(
  curl -sS -c "$COOKIE" -b "$COOKIE" -X POST "$MW_API" \
    -H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8' \
    --data 'action=query&meta=tokens&type=csrf&format=json' \
  | jq -r '.query.tokens.csrftoken'
)"
test -n "$CSRF" && test "$CSRF" != "null"

# 4) Create EICAR file (harmless industry test signature)
cat > e2e_eicar.txt <<'EOF'
X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*
EOF

# 5) Upload (expect: rejected due to antivirus)
RESP="$(
  curl -sS -c "$COOKIE" -b "$COOKIE" -X POST "$MW_API" \
    -H "Accept: application/json" \
    -F "format=json" \
    -F "action=upload" \
    -F "filename=E2E_EICAR.txt" \
    -F "comment=CI E2E ClamAV test (should be blocked)" \
    -F "token=${CSRF}" \
    -F "ignorewarnings=" \
    -F "file=@e2e_eicar.txt"
)"

echo "$RESP" | jq '.' || true

# 6) Assert: MediaWiki returns an error mentioning virus/EICAR
if echo "$RESP" | jq -e '.error' >/dev/null; then
  if echo "$RESP" | jq -r '.error.code,.error.info' | grep -Eiq '(virus|eicar)'; then
    echo "✓ PASS: antivirus blocked the upload"
  else
    echo "::error::Upload was blocked, but not due to antivirus"
    exit 1
  fi
else
  echo "::error::Upload unexpectedly succeeded (virus not detected)"
  exit 1
fi
