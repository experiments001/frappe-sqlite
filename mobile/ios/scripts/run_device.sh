#!/bin/bash
set -euo pipefail

# Build and run on a connected iPhone (requires personal team provisioning)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POC_DIR="$(dirname "$SCRIPT_DIR")/poc"

cd "$POC_DIR"

echo "Building for device..."
briefcase build iOS

echo "Installing to connected device..."
briefcase run iOS -d

echo ""
echo "If device provisioning fails, open the Xcode project:"
echo "  briefcase open iOS"
echo "Then select your personal team and run from Xcode."
