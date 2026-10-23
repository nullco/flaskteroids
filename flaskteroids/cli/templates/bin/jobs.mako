<%text>#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != "start" ]]; then
  echo "Usage: $0 start [CELERY_WORKER_OPTIONS...]" >&2
  exit 1
fi
shift
if [[ ! -x .venv/bin/python ]]; then
  echo "Application environment missing. Run bin/setup first." >&2
  exit 1
fi
exec .venv/bin/python -m celery -A jobs worker --loglevel=info "$@"
</%text>