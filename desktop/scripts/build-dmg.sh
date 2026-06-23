#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SHELL_DIR="$ROOT/desktop/shell/src-tauri"
BUNDLE_DIR="$SHELL_DIR/target/release/bundle"
APP_BUNDLE="$BUNDLE_DIR/macos/frappe-sqlite-desktop.app"
README_SRC="$ROOT/desktop/runtime/resources/README-DMG.txt"
DMG_OUT="$BUNDLE_DIR/dmg/frappe-sqlite-desktop_0.1.0_aarch64.dmg"

echo "==> Step 1: Build PyInstaller sidecar"
"$ROOT/desktop/scripts/build-sidecar.sh"

echo "==> Step 2: Build Tauri app bundle"
cd "$SHELL_DIR"
cargo tauri build

echo "==> Step 3: Re-stage PyInstaller _internal into app bundle"
# PyInstaller 6.x on macOS expects the one-dir contents at
# Contents/Frameworks/ when the executable lives in Contents/MacOS/.
mkdir -p "$APP_BUNDLE/Contents/Frameworks"
rsync -a --delete "$ROOT/dist/frappe-sqlite-macos/_internal/" "$APP_BUNDLE/Contents/Frameworks/"

echo "==> Step 4: Rebuild DMG with README"
WORK="$BUNDLE_DIR/dmg/dmg-build-$$"
MOUNT="$WORK/mount"
mkdir -p "$MOUNT"
rm -f "$DMG_OUT"

SPARSE="$WORK/frappe-sqlite-desktop-temp.sparseimage"
hdiutil create -type SPARSE -size 4g -fs HFS+ -volname "Frappe SQLite Desktop" "$SPARSE"
hdiutil attach "$SPARSE" -nobrowse -mountpoint "$MOUNT"

cp -R "$APP_BUNDLE" "$MOUNT/"
cp "$README_SRC" "$MOUNT/README.txt"

hdiutil detach "$MOUNT"
hdiutil convert "$SPARSE" -format UDZO -o "$DMG_OUT"
rm -rf "$WORK"

echo ""
echo "DMG ready: $DMG_OUT"
ls -lh "$DMG_OUT"
