#!/usr/bin/env bash
# Use the same isolated full-stack checks locally and in CI.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_DIR"
export PYTHONDONTWRITEBYTECODE=1
exec "$PROJECT_DIR/tests/run-python.sh" tests/e2e.py "$@"
