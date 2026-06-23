#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SEED_SOURCE="${FRAPPE_SQLITE_SEED_SOURCE:-}"
LEGACY_SEED_ROOT="${SQLITEPOC_ROOT:-/Users/safwan/Code/docker/fdocker/development/sqlitepoc}"
PYINSTALLER_PYTHON="${PYINSTALLER_PYTHON:-}"

cd "$ROOT"

echo "=== Step 1: Prepare seed site ==="
rm -rf desktop/runtime/resources/seed_site
mkdir -p desktop/runtime/resources/seed_site/sites

if [[ -z "$SEED_SOURCE" ]]; then
  if [[ -d "$ROOT/sites/sqliteonly.localhost" ]]; then
    SEED_SOURCE="$ROOT/sites"
  elif [[ -d "$LEGACY_SEED_ROOT/sites/sqliteonly.localhost" ]]; then
    SEED_SOURCE="$LEGACY_SEED_ROOT/sites"
  else
    echo "No seed site found. Set FRAPPE_SQLITE_SEED_SOURCE to a sites directory containing sqliteonly.localhost." >&2
    exit 1
  fi
fi

if [[ ! -d "$SEED_SOURCE/sqliteonly.localhost" ]]; then
  echo "Seed source missing sqliteonly.localhost: $SEED_SOURCE" >&2
  exit 1
fi

cp -R "$SEED_SOURCE/sqliteonly.localhost" desktop/runtime/resources/seed_site/sites/sqliteonly.localhost

# Ensure the bundled seed site never ships in maintenance mode.
python3 - <<'PY'
import json, pathlib
config = pathlib.Path("desktop/runtime/resources/seed_site/sites/sqliteonly.localhost/site_config.json")
if config.exists():
    data = json.loads(config.read_text())
    data["maintenance_mode"] = 0
    config.write_text(json.dumps(data, indent=1) + "\n")
    print("Reset maintenance_mode to 0 in bundled seed site config")
PY

[[ -f "$SEED_SOURCE/common_site_config.json" ]] && cp "$SEED_SOURCE/common_site_config.json" desktop/runtime/resources/seed_site/sites/common_site_config.json
[[ -f "$SEED_SOURCE/apps.txt" ]] && cp "$SEED_SOURCE/apps.txt" desktop/runtime/resources/seed_site/sites/apps.txt
if [[ -d "$SEED_SOURCE/assets" ]]; then
  rsync -aL --delete "$SEED_SOURCE/assets/" desktop/runtime/resources/seed_site/sites/assets/ || {
    code=$?
    if [[ "$code" != "23" ]]; then
      exit "$code"
    fi
    echo "Warning: rsync returned 23 while copying seed assets; continuing after partial-transfer check."
  }
  test -f desktop/runtime/resources/seed_site/sites/assets/frappe/dist/css/website.bundle.FLBLKNL2.css
fi

echo "=== Step 2: PyInstaller ==="
if [[ -z "$PYINSTALLER_PYTHON" ]]; then
  if [[ -x "$ROOT/.venv-macos/bin/python" ]]; then
    PYINSTALLER_PYTHON="$ROOT/.venv-macos/bin/python"
  elif [[ -x "$LEGACY_SEED_ROOT/.venv-macos/bin/python" ]]; then
    PYINSTALLER_PYTHON="$LEGACY_SEED_ROOT/.venv-macos/bin/python"
  else
    PYINSTALLER_PYTHON="$(command -v python3)"
  fi
fi

rm -rf build dist
"$PYINSTALLER_PYTHON" -m PyInstaller desktop/runtime/pyinstaller/frappe_sqlite.spec --clean --noconfirm

echo ""
echo "Build complete -> dist/frappe-sqlite-macos/frappe-sqlite"
