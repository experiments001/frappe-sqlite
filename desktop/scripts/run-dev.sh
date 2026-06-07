#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${PORT:-8765}"
SITE="${FRAPPE_SITE_NAME:-sqliteonly.localhost}"
DATA_DIR="${FRAPPE_SQLITE_DATA_DIR:-$HOME/Library/Application Support/FrappeSQLite}"

if [[ ! -f "$ROOT/desktop/runtime/runner/main.py" ]]; then
  echo "Missing desktop runtime runner." >&2
  exit 1
fi

export FRAPPE_SITE_NAME="$SITE"
export FRAPPE_SQLITE_DATA_DIR="$DATA_DIR"
python3 "$ROOT/desktop/runtime/runner/main.py" --port "$PORT" --no-browser
