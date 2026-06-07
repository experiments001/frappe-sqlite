#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SHELL_DIR="$ROOT/desktop/shell"

echo "Checking desktop prerequisites..."
command -v node >/dev/null || { echo "Missing node" >&2; exit 1; }
command -v npm >/dev/null || { echo "Missing npm" >&2; exit 1; }
command -v cargo >/dev/null || { echo "Missing Rust cargo" >&2; exit 1; }

if [[ -f "$SHELL_DIR/package.json" ]]; then
  (cd "$SHELL_DIR" && npm install)
else
  echo "No desktop/shell/package.json found; skipping npm install."
fi

echo "Desktop prerequisite check complete."
