#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LEGACY_BENCH="${SQLITEPOC_ROOT:-/Users/safwan/Code/docker/fdocker/development/sqlitepoc}"
OUT="$ROOT/desktop/shell/src-tauri/binaries"
SRC="$LEGACY_BENCH/dist/frappe-sqlite-macos"

if [[ ! -x "$LEGACY_BENCH/desktop_runtime/scripts/build_macos_pyinstaller.sh" ]]; then
  echo "PyInstaller build script not found: $LEGACY_BENCH/desktop_runtime/scripts/build_macos_pyinstaller.sh" >&2
  echo "Set SQLITEPOC_ROOT to a bench/runtime checkout that can build the sidecar." >&2
  exit 1
fi

echo "Building PyInstaller sidecar from: $LEGACY_BENCH"
echo "Note: this is a transitional bridge until PyInstaller spec/resources live under desktop/runtime."
(cd "$LEGACY_BENCH" && ./desktop_runtime/scripts/build_macos_pyinstaller.sh)

if [[ ! -x "$SRC/frappe-sqlite" || ! -d "$SRC/_internal" ]]; then
  echo "PyInstaller output missing under: $SRC" >&2
  exit 1
fi

mkdir -p "$OUT"
cp "$SRC/frappe-sqlite" "$OUT/frappe-sqlite-aarch64-apple-darwin"
rsync -a --delete "$SRC/_internal/" "$OUT/_internal/"

echo "Sidecar staged under: $OUT"
