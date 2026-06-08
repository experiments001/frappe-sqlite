#!/usr/bin/env bash
# Phase 0 — Install Android SDK, NDK, emulator, Rust targets
# Run once on a fresh machine. Safe to re-run.
set -euo pipefail

echo "=== Frappe SQLite Android — Environment Setup ==="

# ── Java 17 ──────────────────────────────────────────────────────────────────
if ! java -version 2>&1 | grep -q "17"; then
  echo "Installing OpenJDK 17..."
  brew install openjdk@17
  echo 'export JAVA_HOME=$(brew --prefix openjdk@17)' >> ~/.zshrc
  export JAVA_HOME=$(brew --prefix openjdk@17)
fi
echo "Java: $(java -version 2>&1 | head -1)"

# ── Android SDK ───────────────────────────────────────────────────────────────
if [ -z "${ANDROID_HOME:-}" ]; then
  export ANDROID_HOME="$HOME/Library/Android/sdk"
  echo "export ANDROID_HOME=$ANDROID_HOME" >> ~/.zshrc
  echo "export PATH=\$ANDROID_HOME/cmdline-tools/latest/bin:\$ANDROID_HOME/platform-tools:\$ANDROID_HOME/emulator:\$PATH" >> ~/.zshrc
fi
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

if ! command -v sdkmanager &>/dev/null; then
  echo "Installing Android command-line tools..."
  brew install --cask android-commandlinetools
fi

echo "Accepting SDK licenses..."
yes | sdkmanager --licenses 2>/dev/null || true

echo "Installing SDK components..."
sdkmanager \
  "platform-tools" \
  "platforms;android-33" \
  "build-tools;33.0.2" \
  "emulator" \
  "system-images;android-33;google_apis;arm64-v8a"

# ── Android NDK ───────────────────────────────────────────────────────────────
NDK_VERSION="25.2.9519653"
sdkmanager "ndk;${NDK_VERSION}"
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/$NDK_VERSION"
echo "export ANDROID_NDK_HOME=$ANDROID_NDK_HOME" >> ~/.zshrc

# ── Rust Android targets ──────────────────────────────────────────────────────
echo "Installing Rust Android targets..."
rustup target add \
  aarch64-linux-android \
  armv7-linux-androideabi \
  x86_64-linux-android \
  i686-linux-android

# ── Tauri CLI v2 ─────────────────────────────────────────────────────────────
if ! cargo tauri --version 2>/dev/null | grep -q "^tauri-cli 2"; then
  echo "Installing tauri-cli v2..."
  cargo install tauri-cli --version "^2"
fi

echo ""
echo "=== Setup complete. Reload your shell: source ~/.zshrc ==="
echo ""
echo "Next: run ./setup-emulator.sh"
