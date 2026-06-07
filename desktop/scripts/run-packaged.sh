#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app"

if [[ ! -d "$APP" ]]; then
  echo "App bundle not found: $APP" >&2
  echo "Run desktop/scripts/build-app.sh and desktop/scripts/sync-sidecar.sh first." >&2
  exit 1
fi

open "$APP"
