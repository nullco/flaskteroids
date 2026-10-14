<%text>#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Prepare once before this web process starts workers, not in every worker.
if [[ "${1:-}" == "gunicorn" && "${2:-}" == "wsgi:app" ]]; then
  mkdir -p storage
  bin/flask db:prepare
fi
exec "$@"
</%text>