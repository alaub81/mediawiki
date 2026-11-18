#!/usr/bin/env bash
# Select a supported interpreter without changing the caller's working directory.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
for candidate in "$PROJECT_DIR/.lint-venv/bin/python" python3.15 python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 &&
    "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    exec "$candidate" "$@"
  fi
done
echo "Python 3.10+ is required for local checks." >&2
exit 1
