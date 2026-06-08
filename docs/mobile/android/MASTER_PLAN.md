# Master Plan — Frappe SQLite on Android

**Goal**: Run Frappe (Python, SQLite, no MariaDB, no Redis) as a native Android app.
**Approach**: Tauri v2 Android shell + Chaquopy (embedded CPython) + Frappe WSGI served in-process on localhost.
**Branch**: `feature/mobile-android-first-run`
**Worktree**: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android`

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Android APK                          │
│                                                         │
│  ┌────────────────────┐   ┌─────────────────────────┐  │
│  │   Tauri v2 Shell   │   │   Chaquopy Python VM    │  │
│  │   (Kotlin + Rust)  │   │   (CPython 3.11)        │  │
│  │                    │   │                         │  │
│  │  WebView           │   │  frappe/                │  │
│  │  └─ 127.0.0.1:8765 │◄──│  werkzeug (WSGI)       │  │
│  │                    │   │  SQLite (built-in)      │  │
│  │  Tauri Commands    │   │  runtime/runner/*.py    │  │
│  │  ├─ get_setup_state│   │                         │  │
│  │  ├─ save_setup     │   │  Thread: serve()        │  │
│  │  └─ start_server   │   │  └─ port 8765           │  │
│  └────────────────────┘   └─────────────────────────┘  │
│                                                         │
│  Data: /data/data/com.frappe.sqlite-mobile/files/       │
│  └─ sites/sqliteonly.localhost/                         │
└─────────────────────────────────────────────────────────┘
```

**Key differences from desktop:**
- No PyInstaller sidecar. Python lives inside the APK via Chaquopy.
- No subprocess spawn. Frappe server runs in a Chaquopy Python thread called from Kotlin.
- No `Library/Application Support`. Data lives in Android app private storage.
- SQLite is Android-native — no extra driver needed.
- Tauri v2 already supports Android via `tauri android` commands (lib.rs has `#[cfg_attr(mobile, tauri::mobile_entry_point)]`).

---

## Repo Structure

```
mobile/
└── android/
    ├── runtime/
    │   ├── runner/
    │   │   ├── main.py           # entry point called from Kotlin
    │   │   ├── server.py         # werkzeug WSGI server
    │   │   ├── migration.py      # seed site + asset copy
    │   │   └── runtime_paths.py  # Android-aware paths
    │   └── resources/
    │       └── seed_site/        # bundled initial site (same as desktop)
    ├── shell/
    │   ├── src-tauri/
    │   │   ├── Cargo.toml
    │   │   ├── build.rs
    │   │   ├── tauri.conf.json
    │   │   └── src/
    │   │       └── lib.rs        # Android-aware, no sidecar spawn
    │   ├── src/
    │   │   └── main.ts           # frontend (same as desktop)
    │   └── package.json
    └── scripts/
        ├── setup-env.sh          # Phase 0: install SDK/NDK/emulator
        ├── setup-emulator.sh     # create + start AVD
        ├── build-debug.sh        # tauri android build --debug
        ├── run-emulator.sh       # start emulator + adb wait
        └── clean-cache.sh        # free disk space
docs/
└── mobile/
    └── android/
        ├── AGENT_LOOP.md         # ← start here every run
        ├── PHASE_TRACKER.md      # ← current state
        ├── MASTER_PLAN.md        # ← this file
        └── BLOCKERS.md           # ← created on first blocker
```

---

## Phase 0 — Environment Setup

**Objective**: Working Android SDK/NDK/emulator + Rust Android targets on the build machine.

### Tasks

#### 0.1 — Install prerequisites

```bash
# Java 17 (required by Gradle)
brew install openjdk@17
echo 'export JAVA_HOME=$(brew --prefix openjdk@17)' >> ~/.zshrc

# Android command-line tools (no Android Studio needed)
brew install --cask android-commandlinetools

# Accept licenses
yes | sdkmanager --licenses

# Install SDK platform + build tools + emulator
sdkmanager \
  "platform-tools" \
  "platforms;android-33" \
  "build-tools;33.0.2" \
  "emulator" \
  "system-images;android-33;google_apis;arm64-v8a"
```

#### 0.2 — Install Android NDK

```bash
sdkmanager "ndk;25.2.9519653"
export ANDROID_NDK_HOME=$ANDROID_HOME/ndk/25.2.9519653
```

#### 0.3 — Install Rust Android targets

```bash
rustup target add \
  aarch64-linux-android \
  armv7-linux-androideabi \
  x86_64-linux-android \
  i686-linux-android
```

#### 0.4 — Create emulator (smallest viable)

```bash
# Pixel 3a with API 33, arm64 — ~2GB download
avdmanager create avd \
  --name frappe_android_dev \
  --package "system-images;android-33;google_apis;arm64-v8a" \
  --device "Nexus 5X" \
  --force

# Start it (headless for CI, with UI for dev)
emulator -avd frappe_android_dev -no-audio &
adb wait-for-device
adb devices
```

#### 0.5 — Install Tauri Android prerequisites

```bash
cargo install tauri-cli --version "^2"
# Verify
cargo tauri android --help
```

### Validation Checklist — Phase 0

```
[ ] java -version         → openjdk 17
[ ] sdkmanager --list     → platforms;android-33 installed
[ ] adb devices           → emulator shows as "device"
[ ] rustup target list --installed | grep android → 4 targets
[ ] cargo tauri --version → 2.x
```

---

## Phase 1 — Tauri Android Shell

**Objective**: A Tauri v2 shell that builds for Android and shows a WebView.

### Tasks

#### 1.1 — Scaffold mobile/android/shell/

Copy and adapt the desktop shell:

```bash
cp -r desktop/shell/ mobile/android/shell/
cd mobile/android/shell/
```

Edit `src-tauri/tauri.conf.json`:
- Change `productName` to `frappe-sqlite-mobile`
- Change `identifier` to `com.frappe.sqlite-mobile`
- Remove `externalBin` (no sidecar on Android)
- Keep `android.debugApplicationIdSuffix`

#### 1.2 — Initialise Tauri Android

```bash
cd mobile/android/shell/
npm install
cargo tauri android init
```

This generates `src-tauri/gen/android/` with a Gradle project.

#### 1.3 — Strip lib.rs to shell-only

On Android, we don't spawn a sidecar subprocess. The Python server starts from Kotlin via Chaquopy. Strip `lib.rs` to:
- Keep `get_setup_state`, `save_setup`, `start_server` Tauri commands
- Remove `start_sidecar_process` (replaced in Phase 3)
- `start_server` will call a Kotlin/JNI bridge instead (Phase 3)
- For Phase 1, `start_server` can return `Ok(())` as a stub

#### 1.4 — Build and run

```bash
cd mobile/android/shell/
cargo tauri android build --debug
# Install
adb install src-tauri/gen/android/app/build/outputs/apk/debug/app-debug.apk
```

### Validation Checklist — Phase 1

```
[ ] cargo tauri android build --debug  → exits 0
[ ] adb install succeeds               → "Success"
[ ] App launches on emulator           → no crash
[ ] WebView visible                    → static "Loading..." page
```

---

## Phase 2 — Python Runtime via Chaquopy

**Objective**: CPython 3.11 + Frappe dependencies embedded in the APK.

### Background

[Chaquopy](https://chaquo.com/chaquopy/) is the standard way to embed Python in an Android app. It integrates via a Gradle plugin and handles:
- Cross-compiled CPython for arm64/x86_64
- pip package installation at build time
- Python `import` resolution inside the APK

### Tasks

#### 2.1 — Add Chaquopy to Gradle

Edit `mobile/android/shell/src-tauri/gen/android/build.gradle`:

```gradle
buildscript {
    repositories {
        maven { url "https://chaquo.com/maven" }
    }
    dependencies {
        classpath "com.chaquo.python:gradle:15.0.1"
    }
}
```

Edit `mobile/android/shell/src-tauri/gen/android/app/build.gradle`:

```gradle
plugins {
    id "com.chaquo.python"
}

android {
    defaultConfig {
        python {
            version "3.11"
            pip {
                // Core Frappe dependencies (no MySQL, no Redis)
                install "werkzeug"
                install "click"
                install "jinja2"
                install "markupsafe"
                install "gitpython"
                install "python-dateutil"
                install "pytz"
                install "six"
                install "semantic-version"
                install "charset-normalizer"
                install "cryptography"
                install "pyjwt"
                install "requests"
                // Frappe itself (from our fork — see note below)
            }
            sourceSet {
                srcDirs "src/main/python"
            }
        }
    }
}
```

**Note on Frappe package**: Frappe is not on PyPI as a standalone package. Options:
1. Copy frappe source into `src/main/python/frappe/` (simplest for quick-and-dirty)
2. Build a wheel from the repo and include it via `install file:...`
3. Use a local path dependency

For quick-and-dirty: copy the `frappe/` directory into `mobile/android/runtime/python_src/` and point Chaquopy's `sourceSet` to it.

#### 2.2 — Frappe dependency audit

Strip dependencies that won't work on Android:
- Remove `PyMySQL` / `mysqlclient` (no MariaDB)
- Remove `redis` (no Redis)
- Remove anything that forks processes or requires system daemons

Key env vars that disable these at runtime (already set in `server.py`):
- `NO_REDIS=1`
- `NO_MARIADB=1`
- `FRAPPE_SQLITE_DESKTOP=1`

#### 2.3 — Smoke test

In a temporary Android Activity or Tauri command, call:

```kotlin
// Kotlin
val python = Python.getInstance()
val module = python.getModule("frappe")
Log.d("Frappe", "Frappe loaded: $module")
```

### Validation Checklist — Phase 2

```
[ ] Gradle sync succeeds with Chaquopy
[ ] APK builds with Python embedded
[ ] `import frappe` does not crash the app
[ ] Logcat shows "Frappe loaded: ..." log line
```

---

## Phase 3 — In-Process Frappe Server

**Objective**: Frappe serves HTTP on 127.0.0.1:8765 inside the running Android app.

### Tasks

#### 3.1 — Write mobile/android/runtime/runner/

These are adapted from `desktop/runtime/runner/` with Android-specific path logic.

**`runtime_paths.py`**:
```python
import os
from pathlib import Path

PRODUCT_NAME = "FrappeSQLite"

def app_data_root() -> Path:
    # Android passes this via environment variable set from Kotlin
    override = os.environ.get("FRAPPE_SQLITE_DATA_DIR")
    if override:
        return Path(override)
    raise RuntimeError("FRAPPE_SQLITE_DATA_DIR not set — must be injected by Kotlin")

def bundle_root() -> Path:
    # On Android, source is extracted by Chaquopy to a known path
    # or we point to the Chaquopy source dir
    override = os.environ.get("FRAPPE_SQLITE_BUNDLE_ROOT")
    if override:
        return Path(override)
    raise RuntimeError("FRAPPE_SQLITE_BUNDLE_ROOT not set")

def sites_path() -> Path:
    return app_data_root() / "sites"

def logs_path() -> Path:
    return app_data_root() / "logs"

def ensure_base_dirs() -> None:
    app_data_root().mkdir(parents=True, exist_ok=True)
    sites_path().mkdir(parents=True, exist_ok=True)
    logs_path().mkdir(parents=True, exist_ok=True)
```

**`server.py`**: identical to desktop version — no changes needed (werkzeug is cross-platform).

**`migration.py`**: identical to desktop version — seed_assets path adapted via `bundle_root()`.

**`main.py`**: adapted — no `webbrowser.open()`, server starts and blocks.

#### 3.2 — Kotlin bridge to start server

In the Tauri-generated Android Activity (or a custom Service):

```kotlin
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform

class MainActivity : TauriActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // Inject Android paths into Python env
        val dataDir = filesDir.absolutePath
        val bundleRoot = "$dataDir/frappe_bundle"
        
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(this))
        }
        
        System.setenv("FRAPPE_SQLITE_DATA_DIR", dataDir)
        System.setenv("FRAPPE_SQLITE_BUNDLE_ROOT", bundleRoot)
        System.setenv("NO_REDIS", "1")
        System.setenv("NO_MARIADB", "1")
        System.setenv("FRAPPE_SQLITE_DESKTOP", "1")
        
        // Start Frappe in background thread
        Thread {
            val py = Python.getInstance()
            val main = py.getModule("main")
            main.callAttr("main")  // blocks — runs werkzeug
        }.start()
        
        super.onCreate(savedInstanceState)
    }
}
```

#### 3.3 — Seed site extraction

The seed site (`sqliteonly.localhost/`) needs to be in the APK assets and extracted to `filesDir` on first run. Add to Chaquopy's `sourceSet` or Android assets:

```
app/src/main/assets/seed_site/
└── sites/
    ├── sqliteonly.localhost/
    │   └── site_config.json
    ├── common_site_config.json
    └── apps.txt
```

Extraction logic goes in `migration.py` — on Android it reads from `AssetManager` via an env-var path.

### Validation Checklist — Phase 3

```
[ ] App launches without crash
[ ] Logcat: "Starting Frappe SQLite on http://127.0.0.1:8765"
[ ] adb shell: curl http://127.0.0.1:8765/login → HTTP 200
[ ] WebView loads http://127.0.0.1:8765/login
[ ] Login page renders (CSS + JS present)
```

---

## Phase 4 — Runtime Paths for Android

**Objective**: All paths resolve correctly; data survives app restarts.

### Tasks

#### 4.1 — Verify path injection

Confirm that `FRAPPE_SQLITE_DATA_DIR` is always set before Python starts.

#### 4.2 — SQLite location

Frappe will create its SQLite DB at:
```
/data/data/com.frappe.sqlite-mobile/files/sites/sqliteonly.localhost/frappe.db
```
Verify this path is created and accessible (no permission errors).

#### 4.3 — Assets path

The `frappe/public/` assets need to be accessible at runtime. Options:
1. Include in Chaquopy sourceSet (preferred — Chaquopy extracts to a known path)
2. Copy from APK assets to `filesDir` on first run

Use option 1: set `FRAPPE_SQLITE_BUNDLE_ROOT` to Chaquopy's extraction path.
Chaquopy extracts Python sources to a deterministic path — discover it via:
```python
import sys; print(sys.path)
```

#### 4.4 — Persistence across restarts

Test:
1. Launch app → setup → creates DB
2. Kill app
3. Re-launch → skips setup → loads existing DB → login works

### Validation Checklist — Phase 4

```
[ ] frappe.db exists at expected path after first run
[ ] App restart: no "seed site not found" error
[ ] App restart: login page loads from existing DB
[ ] adb shell: ls /data/data/com.frappe.sqlite-mobile/files/sites/
[ ] SQLite integrity_check: ok
```

---

## Phase 5 — First-Run Setup Screen

**Objective**: Same UX flow as desktop — setup screen on first launch, login page after.

### Tasks

#### 5.1 — Reuse desktop frontend

The frontend (`desktop/shell/src/main.ts` + `index.html`) handles:
- First-run detection via `get_setup_state`
- Setup form
- Redirect to login after `save_setup`

This is mostly reusable. On Android:
- `data_dir` field can be hidden/pre-filled (Android has no user-writable path picker)
- The Tauri commands (`get_setup_state`, `save_setup`, `start_server`) work the same

#### 5.2 — Android-specific config storage

The `config.json` approach from desktop works fine on Android:
- Path: `/data/data/com.frappe.sqlite-mobile/files/config.json`
- `default_data_dir()` in `lib.rs` must return `filesDir` on Android

Update `lib.rs`:
```rust
fn default_data_dir() -> PathBuf {
    #[cfg(target_os = "android")]
    {
        // On Android, Tauri injects the app's filesDir
        // via the TAURI_ANDROID_FILES_DIR env var or similar
        PathBuf::from(
            std::env::var("FRAPPE_SQLITE_DATA_DIR")
                .unwrap_or_else(|_| "/data/data/com.frappe.sqlite-mobile/files".into())
        )
    }
    #[cfg(not(target_os = "android"))]
    {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("Library")
            .join("Application Support")
            .join(PRODUCT_DIR)
    }
}
```

#### 5.3 — WebView navigation to Frappe

After `save_setup` completes and the server is running, the WebView navigates to `http://127.0.0.1:8765`. The Tauri `setup-complete` event triggers this in the frontend JS (already implemented in the desktop shell).

### Validation Checklist — Phase 5

```
[ ] Fresh install: setup form shown on launch
[ ] Fill form → submit → no JS error
[ ] After submit: WebView loads http://127.0.0.1:8765/login
[ ] Second launch (config exists): goes directly to login
[ ] config.json present at expected path
```

---

## Phase 6 — Smoke Test + PR

**Objective**: Full end-to-end verified. PR opened against `main`.

### Full Smoke Test

```
1. Wipe app data (or fresh emulator)
2. Launch app
3. Setup screen appears
4. Fill: site_name=sqliteonly.localhost, email=admin@example.com, password=admin
5. Submit
6. Login page loads
7. Login with admin credentials
8. Frappe Desk loads
9. Create a new "Note" DocType record
10. Reload app
11. Record still exists
12. Kill + relaunch app → login page, existing data
```

### Validation Checklist — Phase 6

```
[ ] All Phase 0–5 checks pass
[ ] Login page loads in < 10s after setup
[ ] Desk loads (assets served, no 404s)
[ ] DocType record create + persist works
[ ] SQLite PRAGMA integrity_check = "ok"
[ ] App survives background/foreground cycle
[ ] Debug APK file recorded in PR description
[ ] PR opened: feature/mobile-android-first-run → main
```

---

## Disk Space Management

Android SDK + NDK + emulator image is ~8–10GB. If space is tight:

```bash
# Run before any build
./mobile/android/scripts/clean-cache.sh

# What it cleans:
# - Gradle caches (~/.gradle/caches)
# - Android build intermediates
# - Rust incremental build cache
# - pip download cache
# - Xcode DerivedData (macOS)
```

If space is still tight, the agent should delete the emulator system image after testing and re-download for next session (image is re-downloadable via sdkmanager).

---

## References

- Tauri v2 Android guide: https://v2.tauri.app/guides/mobile/android/
- Chaquopy docs: https://chaquo.com/chaquopy/doc/current/
- Existing desktop implementation: `desktop/runtime/runner/` (same branch)
- Desktop Tauri shell: `desktop/shell/src-tauri/` (same branch)
- Desktop build scripts: `desktop/scripts/` (same branch)
- PR #7 (desktop): https://github.com/experiments001/frappe-sqlite/pull/7
