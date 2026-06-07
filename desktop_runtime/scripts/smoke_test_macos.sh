#!/usr/bin/env bash
set -euo pipefail

APP="./dist/frappe-sqlite-macos/frappe-sqlite"
[ -x "$APP" ] || { echo "Executable not found: $APP"; exit 1; }

TEST_DIR="$(pwd)/tmp/test-data"
rm -rf "$TEST_DIR"; mkdir -p "$TEST_DIR"
mkdir -p tmp

echo "Starting app..."
FRAPPE_SQLITE_DATA_DIR="$TEST_DIR" "$APP" --port 8765 --no-browser \
  > tmp/frappe-sqlite.log 2>&1 &
PID=$!
echo "PID: $PID"

sleep 15

echo "Checking HTTP..."
curl -fsI http://127.0.0.1:8765 || {
  echo "FAILED — HTTP not up"
  cat tmp/frappe-sqlite.log
  kill "$PID" || true; exit 1
}

echo "Checking login API..."
curl -fs http://127.0.0.1:8765/api/method/login \
  -X POST -H "Content-Type: application/json" \
  -d '{"usr":"Administrator","pwd":"admin"}' > /dev/null || {
  echo "FAILED — Login API not responding"
  cat tmp/frappe-sqlite.log
  kill "$PID" || true; exit 1
}

echo "Checking no external DB/queue..."
pgrep -x mysqld >/dev/null && echo "WARNING: mysqld running"
pgrep -x redis-server >/dev/null && echo "WARNING: redis-server running"

kill "$PID" || true
echo "Smoke test PASSED."
