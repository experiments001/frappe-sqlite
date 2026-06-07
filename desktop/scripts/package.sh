#!/usr/bin/env bash
set -euo pipefail

echo "Release packaging is not finalized yet."
echo "Expected future flow: build-sidecar.sh -> build-app.sh -> sync-sidecar.sh -> verify-bundle.sh -> sign/notarize -> DMG/zip."
exit 1
