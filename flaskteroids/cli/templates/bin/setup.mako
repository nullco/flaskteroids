<%text>#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/ then run bin/setup." >&2
  exit 1
fi
export FLASKTEROIDS_ENV="${FLASKTEROIDS_ENV-development}"
mkdir -p storage
uv sync
bin/flask db:prepare
printf "%10s  %s\n" ready "Setup complete." next "bin/flask run" next "bin/flask test"
if [[ -d test/system ]]; then
  printf "%10s  %s\n" next "bin/flask test:system"
fi
</%text>