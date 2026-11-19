#!/usr/bin/env bash
# Skins.
set -euo pipefail
# The E2E runner writes this disposable fixture in its temporary directory.
# Load .env.ci without overwriting PATH
# shellcheck source=/dev/null
if [ -f .env.ci ]; then ORIG_PATH="$PATH"; set -a; . ./.env.ci; set +a; export PATH="$ORIG_PATH"; fi
: "${MW_HTTP_PORT:=8080}"
: "${E2E_EXPECT_SKINS:=$(docker compose exec -T mediawiki printenv MW_EXTRA_SKINS | tr -d '\r')}"
[ -n "$E2E_EXPECT_SKINS" ] || { echo "No E2E_EXPECT_SKINS defined, skipping"; exit 0; }

# 1) Define the helper first
norm(){ printf '%s' "$1" | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/[ _]+/-/g; s/[^a-z0-9-]+//g'; }
to_code(){
  n="$(norm "$1")"
  case "$n" in
    vector2022|vector-2022) echo "vector-2022" ;;
    minervaneue|minerva)    echo "minerva" ;;
    monobook)               echo "monobook" ;;
    timeless)               echo "timeless" ;;
    deskmessmirrored|desk*) echo "deskmessmirrored" ;;
    cologneblue|cologne-blue) echo "cologneblue" ;;
    *) echo "$n" ;;
  esac
}

# 2) Build expected skin codes from MW_SKINS, one per line
WANT=""
for s in $E2E_EXPECT_SKINS; do
  c="$(to_code "$s")"
  [ -n "$c" ] && WANT="${WANT}${c}\n"
done

# 3) Get installed and loaded skins from the API, with one name per line
JSON="$(curl -fsS "http://localhost:${MW_HTTP_PORT:-8080}/api.php?action=query&meta=siteinfo&siprop=skins&format=json")"
API_CODES="$(
  printf '%s' "$JSON" \
  | grep -o '"code":"[^"]*"' | cut -d'"' -f4 \
  | while IFS= read -r x; do printf '%s\n' "$(norm "$x")"; done
)"

# 4) Compare exact line matches
fail=0
while IFS= read -r need; do
  [ -z "$need" ] && continue
  if printf '%s\n' "$API_CODES" | grep -qx "$need"; then
    echo "✓ skin loaded: $need"
  else
    echo "::error::skin not loaded: $need"
    fail=1
  fi
done < <(printf '%b' "$WANT")
exit "$fail"
