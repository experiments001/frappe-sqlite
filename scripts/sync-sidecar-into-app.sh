#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/desktop_shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app"
BIN_SRC="$ROOT/desktop_shell/src-tauri/binaries/frappe-sqlite-aarch64-apple-darwin"
INTERNAL_SRC="$ROOT/desktop_shell/src-tauri/binaries/_internal"

if [[ ! -d "$APP" ]]; then
  echo "App bundle not found: $APP" >&2
  exit 1
fi

if [[ ! -x "$BIN_SRC" || ! -d "$INTERNAL_SRC" ]]; then
  echo "Sidecar input missing under desktop_shell/src-tauri/binaries" >&2
  exit 1
fi

mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Frameworks"
cp "$BIN_SRC" "$APP/Contents/MacOS/frappe-sqlite"
rsync -a --delete "$INTERNAL_SRC/" "$APP/Contents/MacOS/_internal/"
rsync -a --delete "$INTERNAL_SRC/" "$APP/Contents/Frameworks/"

echo "Synced PyInstaller sidecar into:"
echo "$APP"
