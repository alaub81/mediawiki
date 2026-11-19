#!/usr/bin/env bash
# Exercise MemcachePHP security behavior using disposable Docker resources.
set -euo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$PROJECT_DIR"
if (( $# != 0 )) && { (( $# != 2 )) || [[ "$1" != --image ]]; }; then
  echo "Usage: ./tests/integration-check.sh [--image EXISTING_IMAGE]" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI and a running Docker daemon are required for integration tests." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Cannot access Docker. Start the daemon and check its socket permissions." >&2
  exit 1
fi
export PYTHONDONTWRITEBYTECODE=1
exec "$PROJECT_DIR/tests/run-python.sh" tests/memcachephp_security_test.py "$@"
