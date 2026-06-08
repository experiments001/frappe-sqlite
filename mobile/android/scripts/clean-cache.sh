#!/usr/bin/env bash
# Free disk space before a large Android build
# Safe to run any time — only clears regenerable caches
set -euo pipefail

echo "=== Frappe SQLite Android — Cache Cleaner ==="
df -h / | tail -1 | awk '{print "Before: " $4 " free"}'

# Gradle build caches
GRADLE_CACHE="$HOME/.gradle/caches"
if [ -d "$GRADLE_CACHE" ]; then
  echo "Clearing Gradle caches: $GRADLE_CACHE"
  rm -rf "$GRADLE_CACHE"
fi

# Android build intermediates in worktree
WORKTREE_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BUILD_DIR="$WORKTREE_ROOT/mobile/android/shell/src-tauri/gen/android/app/build"
if [ -d "$BUILD_DIR" ]; then
  echo "Clearing Android build outputs: $BUILD_DIR"
  rm -rf "$BUILD_DIR"
fi

# Rust incremental build cache
RUST_TARGET="$WORKTREE_ROOT/mobile/android/shell/src-tauri/target"
if [ -d "$RUST_TARGET/debug/incremental" ]; then
  echo "Clearing Rust incremental cache..."
  rm -rf "$RUST_TARGET/debug/incremental"
  rm -rf "$RUST_TARGET/release/incremental"
fi

# pip download cache
PIP_CACHE="$HOME/Library/Caches/pip"
if [ -d "$PIP_CACHE" ]; then
  echo "Clearing pip cache: $PIP_CACHE"
  rm -rf "$PIP_CACHE"
fi

# Xcode DerivedData (macOS — often huge)
DERIVED="$HOME/Library/Developer/Xcode/DerivedData"
if [ -d "$DERIVED" ]; then
  echo "Clearing Xcode DerivedData..."
  rm -rf "$DERIVED"
fi

# Android emulator snapshots (large, always regenerable)
AVD_DIR="$HOME/.android/avd/frappe_android_dev.avd"
SNAP_DIR="$AVD_DIR/snapshots"
if [ -d "$SNAP_DIR" ]; then
  echo "Clearing emulator snapshots: $SNAP_DIR"
  rm -rf "$SNAP_DIR"
fi

echo ""
df -h / | tail -1 | awk '{print "After:  " $4 " free"}'
echo "Done."
