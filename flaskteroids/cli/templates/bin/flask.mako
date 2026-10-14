#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  echo "Application environment missing. Run bin/setup first." >&2
  exit 1
fi
# Asset builds must not boot the app or require runtime credentials/database.
if [[ $# -gt 0 && "$1" == "assets:precompile" ]]; then
  exec .venv/bin/python -m flaskteroids "$@"
fi
# Replace this process so Flask receives arguments, signals, and exit status directly.
exec .venv/bin/python -m flask "$@"
