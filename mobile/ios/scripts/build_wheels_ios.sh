#!/bin/bash
set -euo pipefail

# Build iOS wheels for Frappe SQLite runtime deps
# Usage: ./build_wheels_ios.sh [simulator|device|all]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_ROOT="$(dirname "$SCRIPT_DIR")"
WHEELHOUSE="$IOS_ROOT/vendor/wheelhouse"
TARGET="${1:-simulator}"
PYTHON="${PYTHON:-python3.13}"

mkdir -p "$WHEELHOUSE"

# Determine arch based on target
case "$TARGET" in
    simulator)
        ARCH="arm64_iphonesimulator"
        echo "Building simulator wheels (arm64_iphonesimulator)..."
        ;;
    device)
        ARCH="arm64_iphoneos"
        echo "Building device wheels (arm64_iphoneos)..."
        ;;
    all)
        echo "Building all architectures..."
        "$0" simulator
        "$0" device
        exit 0
        ;;
    *)
        echo "Usage: $0 [simulator|device|all]"
        exit 1
        ;;
esac

# Verify tools
if ! command -v cibuildwheel &>/dev/null && ! $PYTHON -m cibuildwheel --version &>/dev/null; then
    echo "ERROR: cibuildwheel not found. Install with:"
    echo "  $PYTHON -m pip install cibuildwheel"
    exit 1
fi

if ! command -v rustup &>/dev/null; then
    echo "ERROR: rustup not found. Install Rust first."
    exit 1
fi

# Ensure Rust iOS targets
rustup target add aarch64-apple-ios aarch64-apple-ios-sim x86_64-apple-ios 2>/dev/null || true

# Export for cibuildwheel
export CIBW_PLATFORM=ios
export CIBW_ARCHS="$ARCH"
export CIBW_BUILD="cp313-*"

# Build wheels from requirements
# Note: cibuildwheel builds individual packages. For bulk building,
# we iterate over requirements and build each.
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

echo "Building wheels from: $REQUIREMENTS"
echo "Output directory: $WHEELHOUSE"
echo ""

# Phase 1: Build the hardest wheels first (in dependency order)
HARD_WHEELS=(
    "cryptography"
    "pydantic-core"
    "MarkupSafe"
    "bcrypt"
    "PyYAML"
    "PyMySQL"
    "pydantic"
    "pypdf"
)

echo "=== Phase 1: Hard wheels ==="
for pkg in "${HARD_WHEELS[@]}"; do
    echo ""
    echo "--- Building: $pkg ---"
    # Extract version constraint from requirements.txt
    constraint=$(grep "^$pkg" "$REQUIREMENTS" || true)
    if [ -z "$constraint" ]; then
        echo "SKIP: $pkg not in requirements.txt"
        continue
    fi
    echo "Constraint: $constraint"
    
    # Build just this package
    $PYTHON -m pip wheel \
        --no-deps \
        --wheel-dir "$WHEELHOUSE" \
        "$constraint" 2>&1 || {
        echo "WARNING: Failed to build $pkg — will need manual intervention or stub"
    }
done

echo ""
echo "=== Phase 2: Pure-Python wheels (bulk) ==="
# For pure-Python packages, we can just pip wheel them
$PYTHON -m pip wheel \
    --no-deps \
    --wheel-dir "$WHEELHOUSE" \
    -r "$REQUIREMENTS" 2>&1 || {
    echo "WARNING: Some pure-Python wheels failed — check output above"
}

echo ""
echo "=== Build complete ==="
echo "Wheels in: $WHEELHOUSE"
ls -la "$WHEELHOUSE"/*.whl 2>/dev/null | wc -l | xargs echo "Total wheels:"
echo ""
echo "Missing wheels (check for failures above):"
for pkg in $(grep '^[A-Za-z]' "$REQUIREMENTS" | sed 's/[=~<>!].*//'); do
    if ! ls "$WHEELHOUSE/${pkg}"*.whl 1>/dev/null 2>&1 && \
       ! ls "$WHEELHOUSE/${pkg,,}"*.whl 1>/dev/null 2>&1 && \
       ! ls "$WHEELHOUSE/${pkg//-/_}"*.whl 1>/dev/null 2>&1; then
        echo "  MISSING: $pkg"
    fi
done
