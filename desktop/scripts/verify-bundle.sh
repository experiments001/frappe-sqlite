#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app"
MARKERS='BEGIN IMMEDIATE|_BUSY_TIMEOUT_MS|cache_size = -32768|mmap_size = 134217728|_NAMED_PARAM_RE|journal_mode = WAL'

SOURCE_DB="$ROOT/frappe/database/sqlite/database.py"
STAGED_DB="$ROOT/desktop/shell/src-tauri/binaries/_internal/frappe/database/sqlite/database.py"
APP_DB="$APP/Contents/MacOS/_internal/frappe/database/sqlite/database.py"

for path in "$SOURCE_DB" "$STAGED_DB" "$APP_DB"; do
  [[ -f "$path" ]] || { echo "Missing SQLite runtime file: $path" >&2; exit 1; }
done

echo "SQLite database.py hashes:"
shasum -a 256 "$SOURCE_DB" "$STAGED_DB" "$APP_DB"

source_hash="$(shasum -a 256 "$SOURCE_DB" | awk '{print $1}')"
staged_hash="$(shasum -a 256 "$STAGED_DB" | awk '{print $1}')"
app_hash="$(shasum -a 256 "$APP_DB" | awk '{print $1}')"

if [[ "$source_hash" != "$staged_hash" || "$source_hash" != "$app_hash" ]]; then
  echo "Bundle is stale: SQLite source/staging/app hashes differ." >&2
  exit 1
fi

rg -n "$MARKERS" \
  "$ROOT/frappe/database/sqlite/database.py" \
  "$ROOT/frappe/database/sqlite/setup_db.py" \
  "$ROOT/desktop/shell/src-tauri/binaries/_internal/frappe/database/sqlite/database.py" \
  "$ROOT/desktop/shell/src-tauri/binaries/_internal/frappe/database/sqlite/setup_db.py" \
  "$APP/Contents/MacOS/_internal/frappe/database/sqlite/database.py" \
  "$APP/Contents/MacOS/_internal/frappe/database/sqlite/setup_db.py" >/dev/null

echo "Bundle freshness verified."
