<%text>#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/ then run bin/setup." >&2
  exit 1
fi
export FLASK_ENV="${FLASK_ENV-development}"
mkdir -p storage
uv sync
bin/flask db:prepare
echo "Setup complete. Run bin/flask run, bin/flask test, and bin/flask test:system."
</%text>