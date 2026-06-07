#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/desktop/shell/src-tauri/binaries"
SRC="$ROOT/dist/frappe-sqlite-macos"
BUILD_SCRIPT="$ROOT/desktop/runtime/scripts/build_macos_pyinstaller.sh"

if [[ ! -x "$BUILD_SCRIPT" ]]; then
  echo "PyInstaller build script not found or not executable: $BUILD_SCRIPT" >&2
  exit 1
fi

echo "Building PyInstaller sidecar from: $ROOT"
"$BUILD_SCRIPT"

if [[ ! -x "$SRC/frappe-sqlite" || ! -d "$SRC/_internal" ]]; then
  echo "PyInstaller output missing under: $SRC" >&2
  exit 1
fi

mkdir -p "$OUT"
cp "$SRC/frappe-sqlite" "$OUT/frappe-sqlite-aarch64-apple-darwin"
rsync -a --delete "$SRC/_internal/" "$OUT/_internal/"

echo "Sidecar staged under: $OUT"
