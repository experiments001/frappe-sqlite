#!/usr/bin/env bash
# Create and start the Android emulator for Frappe SQLite dev
# AVD: frappe_android_dev  |  Pixel 5 API 33  |  arm64-v8a
set -euo pipefail

AVD_NAME="frappe_android_dev"
PACKAGE="system-images;android-33;google_apis;arm64-v8a"
DEVICE="pixel_5"

export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH"

# Create AVD if it doesn't exist
if ! avdmanager list avd 2>/dev/null | grep -q "$AVD_NAME"; then
  echo "Creating AVD: $AVD_NAME ..."
  avdmanager create avd \
    --name "$AVD_NAME" \
    --package "$PACKAGE" \
    --device "$DEVICE" \
    --force
  echo "AVD created."
else
  echo "AVD '$AVD_NAME' already exists."
fi

# Check if already running
if adb devices 2>/dev/null | grep -q "emulator"; then
  echo "Emulator already running:"
  adb devices
  exit 0
fi

echo "Starting emulator (background)..."
emulator -avd "$AVD_NAME" -no-audio -no-boot-anim &
EMULATOR_PID=$!

echo "Waiting for device to be ready (this takes ~60s)..."
adb wait-for-device

# Wait for boot completed
echo "Waiting for Android boot..."
for i in $(seq 1 60); do
  BOOT=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
  if [ "$BOOT" = "1" ]; then
    echo "Emulator ready!"
    break
  fi
  sleep 2
done

echo ""
adb devices
echo ""
echo "Emulator PID: $EMULATOR_PID"
echo "To stop: adb emu kill"
