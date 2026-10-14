<%text>#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  migrate)
    [[ $# -eq 1 ]] || { echo "Usage: $0 migrate" >&2; exit 1; }
    mkdir -p storage
    exec bin/flask db:prepare
    ;;
  *)
    echo "Usage: $0 migrate" >&2
    exit 1
    ;;
esac
</%text>