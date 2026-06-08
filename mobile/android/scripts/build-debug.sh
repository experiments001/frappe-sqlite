#!/usr/bin/env bash
# Phase 1+ — Build debug APK and install on running emulator
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SHELL_DIR="$SCRIPT_DIR/../shell"
WORKTREE_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$ANDROID_HOME/ndk/25.2.9519653}"
export PATH="$ANDROID_HOME/platform-tools:$PATH"

echo "=== Building debug APK ==="
echo "Shell dir: $SHELL_DIR"

# Verify emulator is running
if ! adb devices | grep -q "emulator"; then
  echo "ERROR: No emulator running. Run ./setup-emulator.sh first." >&2
  exit 1
fi

cd "$SHELL_DIR"

# Install npm deps if needed
if [ ! -d node_modules ]; then
  npm install
fi

# Build
cargo tauri android build --debug

APK="$SHELL_DIR/src-tauri/gen/android/app/build/outputs/apk/debug/app-debug.apk"
if [ ! -f "$APK" ]; then
  echo "ERROR: APK not found at $APK" >&2
  exit 1
fi

echo ""
echo "=== Installing APK on emulator ==="
adb install -r "$APK"

echo ""
echo "=== Launching app ==="
adb shell am start -n com.frappe.sqlite-mobile.debug/com.frappe.sqlitemobile.MainActivity 2>/dev/null || true

echo ""
echo "APK: $APK"
echo "Size: $(du -sh "$APK" | cut -f1)"
echo ""
echo "Done. Watch logs with: adb logcat -s tauri frappe python"
