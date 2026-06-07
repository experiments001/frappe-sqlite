#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SHELL_DIR="$ROOT/desktop/shell"

if [[ -f "$SHELL_DIR/package.json" ]]; then
  (cd "$SHELL_DIR" && npm run build)
else
  echo "No desktop/shell/package.json found; skipping frontend build."
fi

if [[ ! -f "$SHELL_DIR/src-tauri/Cargo.toml" ]]; then
  echo "Missing Tauri Cargo.toml: $SHELL_DIR/src-tauri/Cargo.toml" >&2
  exit 1
fi

if [[ -f "$SHELL_DIR/src-tauri/tauri.conf.json" || -f "$SHELL_DIR/src-tauri/Tauri.toml" ]]; then
  (cd "$SHELL_DIR/src-tauri" && cargo tauri build)
else
  echo "No Tauri config found under desktop/shell/src-tauri." >&2
  echo "Current PoC can sync into an existing app bundle, but a fresh app build needs tauri.conf.json/Tauri.toml restored." >&2
  exit 1
fi
