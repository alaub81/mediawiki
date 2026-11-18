#!/usr/bin/env bash
# Run offline tool regressions and resolve example Compose files without containers.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_DIR"
if (( $# != 0 )); then
  echo "Usage: ./tests/test-check.sh" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "Docker CLI with the Compose v2 plugin is required; no running daemon is needed." >&2
  exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PROJECT_DIR/tests${PYTHONPATH:+:$PYTHONPATH}"
exec "$PROJECT_DIR/tests/run-python.sh" -m unittest discover -s tests -p 'test_*.py'
