#!/bin/bash
set -euo pipefail

# Build and run on iOS Simulator (Lane A: Briefcase)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POC_DIR="$(dirname "$SCRIPT_DIR")/poc"

cd "$POC_DIR"

echo "Creating Briefcase iOS project..."
briefcase create iOS

echo "Building Briefcase iOS app..."
briefcase build iOS

echo "Running on Simulator..."
briefcase run iOS
