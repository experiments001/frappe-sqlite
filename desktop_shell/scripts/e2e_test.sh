#!/usr/bin/env bash
set -euo pipefail

APP="src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app/Contents/MacOS/app"
[ -x "$APP" ] || { echo "App not found at $APP"; exit 1; }

echo "Clearing app data..."
rm -rf ~/Library/Application\ Support/FrappeSQLite/
pkill -f "frappe-sqlite" 2>/dev/null || true
sleep 1

echo "Opening app..."
# Run detached from shell job control to avoid macOS job-control kills
(
  "$APP" > /tmp/frappe-e2e.log 2>&1 &
  disown
)

# Give the sidecar time to seed the site and start Frappe
sleep 35

echo "Checking HTTP on port 8765..."
RESPONSE=$(curl -fs http://127.0.0.1:8765/login || true)
if echo "$RESPONSE" | grep -q "<title>Login</title>"; then
  echo "E2E test PASSED — Frappe login page served"
else
  echo "FAILED — Login page not found"
  echo "--- App log ---"
  cat /tmp/frappe-e2e.log || true
  pkill -f "frappe-sqlite" 2>/dev/null || true
  exit 1
fi

pkill -f "frappe-sqlite" 2>/dev/null || true
echo "Cleanup complete"
