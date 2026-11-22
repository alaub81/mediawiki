#!/usr/bin/env bash
# Upload headers, script blocking and untrusted override protection.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# shellcheck source=/dev/null
[ -f .env.ci ] && { set -a; . ./.env.ci; set +a; }
: "${MW_HTTP_PORT:=8080}"
BASE="http://localhost:${MW_HTTP_PORT}"
FIXTURE=$(docker compose exec -T -u www-data mediawiki \
  mktemp -d /var/www/html/images/ci-security.XXXXXXXX)
cleanup() {
  docker compose exec -T -u www-data mediawiki rm -rf -- "$FIXTURE"
}
trap cleanup EXIT

docker compose exec -T -u www-data mediawiki sh -s -- "$FIXTURE" <<'SH'
set -eu
printf 'upload-security-ok' > "$1/static.txt"
printf '<?php echo "unexpected-script-execution";' > "$1/probe.php"
cp "$1/probe.php" "$1/probe.php.jpg"
printf 'private' > "$1/.hidden"
# Any interpretation of this file would cause HTTP 500.
printf 'InvalidUploadOverrideDirective On\n' > "$1/.htaccess"
SH

URL="$BASE/images/${FIXTURE##*/}"
if [[ "$(curl -fsS "$URL/static.txt")" != "upload-security-ok" ]]; then
  echo "::error::static upload was not served with an ignored .htaccess"
  exit 1
fi
HEADERS=$(curl -fsSI "$URL/static.txt")
if ! grep -qi '^X-Content-Type-Options: *nosniff' <<< "$HEADERS"; then
  echo "::error::nosniff header missing on upload"
  exit 1
fi
if ! grep -qi '^Content-Security-Policy:.*sandbox' <<< "$HEADERS"; then
  echo "::error::sandbox policy missing on upload"
  exit 1
fi
for file in probe.php probe.php.jpg .hidden .htaccess; do
  status=$(curl -sS -o /dev/null -w '%{http_code}' "$URL/$file")
  if [[ "$status" != 403 ]]; then
    echo "::error::expected HTTP 403 for $file, got $status"
    exit 1
  fi
done

echo "Upload headers, script blocking and AllowOverride None OK"
