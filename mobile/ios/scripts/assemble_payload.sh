#!/bin/bash
set -euo pipefail

# Assemble app payload: frappe/ + sites/assets + seed site + shims
# Usage: ./assemble_payload.sh [output_dir]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_ROOT="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(cd "$IOS_ROOT/../.." && pwd)"
OUTPUT="${1:-$IOS_ROOT/vendor/app_payload}"

echo "Assembling app payload..."
echo "  Source repo: $REPO_ROOT"
echo "  Output:      $OUTPUT"

rm -rf "$OUTPUT"
mkdir -p "$OUTPUT/apps" "$OUTPUT/sites" "$OUTPUT/shims"

# 1. Copy frappe/ core (same as Android/desktop)
echo "[1/5] Copying frappe/ core..."
cp -R "$REPO_ROOT/frappe" "$OUTPUT/apps/frappe"

# 2. Copy prebuilt assets (from Android seed site or desktop build)
SEED_SITE="$REPO_ROOT/mobile/android/runtime/resources/seed_site"
if [ -d "$SEED_SITE" ]; then
    echo "[2/5] Copying seed site from Android runtime..."
    cp -R "$SEED_SITE/sites" "$OUTPUT/sites_raw"
else
    echo "[2/5] WARNING: No seed site found at $SEED_SITE"
    echo "        Create one with: bench --site sqliteonly.localhost migrate"
fi

# 3. Copy wheelhouse contents (unzipped for embedded Python)
WHEELHOUSE="$IOS_ROOT/vendor/wheelhouse"
if [ -d "$WHEELHOUSE" ] && [ "$(ls -A "$WHEELHOUSE"/*.whl 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "[3/5] Unpacking wheels..."
    mkdir -p "$OUTPUT/python/lib"
    for whl in "$WHEELHOUSE"/*.whl; do
        # Only unpack pure-Python wheels; skip platform-specific ones
        if unzip -l "$whl" | grep -q 'platlib\|\.so\|\.dylib'; then
            echo "  SKIP (platform-specific): $(basename "$whl")"
        else
            unzip -q -o "$whl" -d "$OUTPUT/python/lib" || true
        fi
    done
else
    echo "[3/5] WARNING: No wheels found in $WHEELHOUSE"
fi

# 4. Copy iOS runtime entrypoint
echo "[4/5] Copying iOS runtime..."
cp -R "$IOS_ROOT/runtime" "$OUTPUT/"

# 5. Copy native shims
echo "[5/5] Copying native shims..."
SHIMS="$IOS_ROOT/poc/src/frappe_ios/shims"
if [ -d "$SHIMS" ]; then
    cp -R "$SHIMS/"* "$OUTPUT/shims/"
fi

echo ""
echo "Payload assembled at: $OUTPUT"
echo "Contents:"
find "$OUTPUT" -maxdepth 2 -type d | sort
