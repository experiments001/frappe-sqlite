# AGENTS.md

This project is a Frappe-compatible fork with optional SQLite support and optional host-native macOS desktop packaging **plus Android mobile packaging**. Read this file before making changes.

## Core Intent

SQLite support must stay inside normal Frappe runtime paths and remain opt-in through site config/environment config. The desktop app must run on the host Mac, outside Docker. The Android app must run on-device with no external server.

Runtime targets:

| Platform | Shell | Python | Data Dir |
|----------|-------|--------|----------|
| macOS Desktop | Tauri | PyInstaller sidecar | `~/Library/Application Support/FrappeSQLite/` |
| Android | Tauri + WebView | Chaquopy 3.11 | `/data/data/<pkg>/files/` |
| iOS | Briefcase + WKWebView | Python-Apple-support 3.13 | App sandbox `Documents/` |

Shared constraints:
- No MariaDB
- No Redis
- No Docker
- No bench process required at app runtime
- One `frappe/` core shared by both platforms

Docker may be used only as historical/reference validation for the separate SQLite bench POC. Do not make the desktop app depend on Docker.

---

## Architecture: Shared Core + Platform Layers

```
frappe/  ←── shared core framework (patched for 3.11 + SQLite)
  │
  ├──► desktop/ ──► desktop/runtime/runner/ ──► PyInstaller ──► .app
  │
  └──► mobile/android/ ──► mobile/android/runtime/runner/ ──► Chaquopy ──► .apk
```

### Rule: `frappe/` is shared

Both desktop and mobile consume the **same `frappe/` source tree**. The Android build symlinks it:

```
mobile/android/shell/src-tauri/gen/android/app/src/main/python/frappe
  → ../../../../../../../../../../frappe
```

Any patch to `frappe/` affects **both platforms**. There is no copy. This is why `CORE_CHANGES.md` exists — every `frappe/` modification is a cross-platform contract.

### Rule: Platform layers are consumers, not owners

`desktop/` and `mobile/android/` provide:
- Tauri shell + WebView
- Python runtime bootstrap (`runner/`)
- Build pipeline (PyInstaller / Chaquopy)
- Platform-specific native shims (Android only)

They must **not** define core Frappe behavior.

---

## Important Paths

### Shared core
- **Project root:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android`
- **SQLite backend:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/frappe/database/sqlite`
- **Core changes catalog:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/CORE_CHANGES.md`

### macOS Desktop
- **Desktop root:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop`
- **Tauri shell:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop/shell`
- **Tauri Rust/backend config:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop/shell/src-tauri`
- **Python desktop runtime:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop/runtime`
- **Desktop scripts:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop/scripts`
- **Built app:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app`
- **Historical PyInstaller build checkout:** `/Users/safwan/Code/docker/fdocker/development/sqlitepoc`

### Android
- **Android root:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android`
- **Tauri Android shell:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/shell`
- **Kotlin main activity:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/shell/src-tauri/gen/android/app/src/main/java/com/frappe/sqlite_mobile/MainActivity.kt`
- **Python Android runtime:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/runtime`
- **Chaquopy config:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/shell/src-tauri/gen/android/app/chaquopy.gradle`
- **Native shims:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/shell/src-tauri/gen/android/app/src/main/python/`
- **Seed site (pre-built DB):** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/runtime/resources/seed_site/`
- **Built APK:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/shell/src-tauri/gen/android/app/build/outputs/apk/universal/debug/app-universal-debug.apk`
### iOS
- **iOS root:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/ios`
- **Briefcase PoC:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/ios/poc`
- **iOS runtime:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/ios/runtime`
- **Native shims:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/ios/poc/src/frappe_ios/shims`
- **Python xcframework:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/ios/vendor/Python.xcframework`
- **Wheelhouse:** `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/ios/vendor/wheelhouse`

---

## Platform Runtime Differences

| Aspect | Desktop | Mobile |
|--------|---------|--------|
| **Entry point** | `desktop/runtime/runner/main.py` (argparse) | `mobile/android/runtime/runner/main.py` (Kotlin → Chaquopy) |
| **Server** | Werkzeug `127.0.0.1:8765` | Werkzeug `127.0.0.1:8765` |
| **Paths** | `~/Library/Application Support/FrappeSQLite/` | Env vars from Kotlin (`FRAPPE_SQLITE_DATA_DIR`) |
| **Python** | Host Python 3.12+ | Chaquopy Python 3.11 |
| **Bundle** | PyInstaller `_internal/` | Chaquopy `AssetFinder` (APK zip) |
| **Native deps** | Full wheels | Pure-Python shims (`nh3`, `orjson`, `redis`, `rq`, `PIL`) | Pure-Python shims (`shims/` dir) |
| **Seed strategy** | Filesystem `desktop/runtime/resources/seed_site/` | APK assets extracted by Kotlin | App bundle → `Documents/` on first run |

The **only** files that truly differ per platform are in `*/runtime/runner/`:
- `main.py` — invocation method
- `runtime_paths.py` — data directory abstraction
- `migration.py` — asset source (filesystem vs APK)

`server.py` is ~90% identical. Everything in `frappe/` is shared.

---

## Android Native Shims

These pure-Python files shadow missing native packages inside Chaquopy's `sys.path`:

| Shim | Replaces | Why |
|------|----------|-----|
| `nh3.py` | `nh3` (Rust HTML sanitizer) | No Android wheel |
| `orjson.py` | `orjson` (Rust JSON) | No Android wheel |
| `PIL.py` | `Pillow` (C imaging libs) | No Android wheel |
| `psutil.py` | `psutil` (C system info) | No Android wheel |
| `redis/` | `redis-py` | No Redis server on Android |
| `rq/` | `rq` (Redis Queue) | No Redis server on Android |

Chaquopy puts `app/src/main/python/` before site-packages, so these shims win at import time without modifying `frappe/` code.

---

## Do Not Do These Things

Do not remove `.dist-info`, `.egg-info`, `METADATA`, `RECORD`, or package metadata directories from PyInstaller `_internal`.

These are runtime data. Python packages use them through `importlib.metadata`, package resource lookup, plugin discovery, entry points, and version checks. Removing them can cause failures such as:

```text
ModuleNotFoundError: No module named 'pkg_resources'
PackageNotFoundError
```

Do not make code signing pass by deleting Python metadata. If `codesign` fails, capture the exact failing file/error and fix that specific signing issue.

Do not change the desktop app to call Docker, `bench serve`, MariaDB, Redis, Supervisor, or a container-only path.

Do not assume the Docker SQLite POC URL is the desktop runtime. The desktop runtime should serve from the PyInstaller sidecar on host localhost, normally `127.0.0.1:8765`.

Do not remove the `socket.getfqdn` workaround in `desktop/runtime/runner/server.py` unless you have reproduced and fixed the macOS `.app` sidecar startup hang another way.

Do not commit, push, delete files, or run destructive cleanup unless explicitly instructed.

Do not touch secrets, signing identities, keychains, provisioning profiles, or user credentials without explicit permission.

---

## Known Packaging Issue (Desktop)

After signing/package cleanup, the app may fail with:

```text
ModuleNotFoundError: No module named 'pkg_resources'
```

Current diagnosis:

- Raw PyInstaller output has `semantic_version-2.10.0.dist-info`.
- The current signed `.app` bundle may not have that metadata under `Contents/MacOS/_internal`.
- The `.app` bundle may also lack `pkg_resources`.
- This points to the app-bundle copy/signing cleanup step, not SQLite itself.

Primary fix:

1. Preserve all PyInstaller `_internal/*.dist-info` and related metadata in the `.app` bundle.
2. Add defensive PyInstaller spec entries for `semantic_version`, `setuptools`, and `pkg_resources`.
3. Rebuild the sidecar/app.
4. Sign Mach-O binaries and the app without deleting metadata.
5. Test sidecar and GUI launch on the host Mac.

Patch idea for the PyInstaller spec, currently in the historical `sqlitepoc` build checkout:

```python
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

# later, after datas/hiddenimports are initialized
datas += copy_metadata("semantic_version")
datas += copy_metadata("setuptools")

hiddenimports += [
    "pkg_resources",
    "setuptools",
    "semantic_version",
]
```

---

## Required Verification (Desktop)

After any packaging/signing change, run host-native tests.

Check raw dist metadata:

```bash
find /Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/dist/frappe-sqlite-macos/_internal -maxdepth 1 -name '*semantic*' -print
```

Check app bundle metadata:

```bash
APP=/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app
find "$APP/Contents/MacOS/_internal" -maxdepth 1 -name '*semantic*' -print
find "$APP/Contents/MacOS/_internal" -maxdepth 2 -path '*pkg_resources*' -print
```

Run sidecar directly:

```bash
APP=/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app
"$APP/Contents/MacOS/frappe-sqlite" --port 8766 --no-browser
```

In another shell:

```bash
curl -I http://127.0.0.1:8766/login
```

Expected:

```text
HTTP/1.1 200 OK
```

Run Tauri E2E:

```bash
cd /Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android
./desktop/scripts/verify-bundle.sh
```

Expected:

```text
Bundle freshness verified.
```

This freshness check does not replace the host browser smoke test. Also run the sidecar directly and verify `/login` plus CSS/JS assets.

Launch app:

```bash
open /Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app
```

Manual checks:

- Window opens.
- Sidecar listens on `127.0.0.1:8765`.
- Login page loads.
- Administrator login works with password `admin` if using the seeded POC site.
- Basic create/update/delete works.
- Data persists after quit and relaunch.

---

## Required Verification (Android)

After any Python or Kotlin change:

Build debug APK:

```bash
cd /Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/shell
cargo tauri android build --debug
```

Install and clear data:

```bash
APK="/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/android/shell/src-tauri/gen/android/app/build/outputs/apk/universal/debug/app-universal-debug.apk"
adb install -r "$APK"
adb shell pm clear com.frappe.sqlite_mobile.debug
adb shell am start -n com.frappe.sqlite_mobile.debug/com.frappe.sqlite_mobile.MainActivity
```

Verify APIs:

```bash
adb forward tcp:8765 tcp:8765
curl -X POST http://127.0.0.1:8765/api/method/login -d "usr=Administrator&pwd=admin"
curl http://127.0.0.1:8765/api/method/frappe.desk.doctype.event.event.get_events?start=2026-06-01\&end=2026-06-30
```

Check logcat for `fromisoformat` or crash errors:

```bash
adb logcat -d | grep -iE "frappe|python|ERROR|crash"
```

---

---

## Required Verification (iOS)

After any Python or Swift change:

Build debug app for Simulator:

```bash
cd /Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/ios/poc
source ../.venv/bin/activate
briefcase create iOS
briefcase build iOS
briefcase run iOS
```

Verify APIs (from host, with Simulator running):

```bash
curl -X POST http://127.0.0.1:8765/api/method/login -d "usr=Administrator&pwd=admin"
curl http://127.0.0.1:8765/api/method/frappe.desk.doctype.event.event.get_events
```

Check for crashes in Simulator logs:

```bash
xcrun simctl spawn booted log stream --predicate 'process == "FrappeSQLite"'
```


## Reference Docs

- Current handoff: `/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/docs/tauri-desktop-sqlite-handoff.md`
- SQLite POC handoff: `/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc/docs/sqlite-only-runtime-agent-handoff.md`
- Coverage tracker: `/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc/docs/sqlite-full-coverage-tracker.md`
- Core changes catalog: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/CORE_CHANGES.md`

---

## Agent Operating Rules

Before editing, read this file and inspect the current app bundle contents.

Prefer small scoped changes. Preserve the working SQLite runtime behavior. If a fix requires changing packaging and runtime code at the same time, document why.

When modifying `frappe/`, remember it is **shared** by both desktop and mobile. Test both platforms if the change affects runtime behavior.

When reporting back, include:

- Files changed
- Commands run
- Test results
- Whether the app was tested outside Docker
- Remaining risks
