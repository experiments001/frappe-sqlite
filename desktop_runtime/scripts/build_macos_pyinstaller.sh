#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."   # bench root

echo "=== Step 1: Prepare seed site ==="
rm -rf desktop_runtime/resources/seed_site
mkdir -p desktop_runtime/resources/seed_site/sites

cp -R sites/sqliteonly.localhost desktop_runtime/resources/seed_site/sites/sqliteonly.localhost
[ -f sites/common_site_config.json ] && \
  cp sites/common_site_config.json \
     desktop_runtime/resources/seed_site/sites/common_site_config.json
[ -f sites/apps.txt ] && \
  cp sites/apps.txt \
     desktop_runtime/resources/seed_site/sites/apps.txt

echo "=== Step 2: PyInstaller ==="
source .venv-macos/bin/activate
rm -rf build dist
pyinstaller desktop_runtime/pyinstaller/erpnext_sqlite.spec --clean --noconfirm

echo ""
echo "Build complete → dist/frappe-sqlite-macos/frappe-sqlite"
