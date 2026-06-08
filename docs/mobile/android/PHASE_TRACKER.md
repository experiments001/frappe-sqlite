# Phase Tracker — Android

**Current Phase: 1 — Tauri Android Shell**
**Status: IN PROGRESS**

---

## Phase 0 — Environment Setup

| Task | Status | Notes |
|------|--------|-------|
| Install Android SDK (API 33, arm64) | ✅ | Via `sdkmanager` — already present |
| Install Android NDK r25c or later | ✅ | NDK 25.2.9519653 installed |
| Install emulator image (Pixel_3a API 33 arm64) | ✅ | `system-images;android-33;google_apis;arm64-v8a` |
| `avdmanager` AVD created + boots | ✅ | `frappe_android_dev` AVD, cold boot OK |
| `adb devices` shows emulator | ✅ | `emulator-5554` device |
| Rust Android targets installed | ✅ | 4 targets: aarch64, armv7, x86_64, i686 |
| `tauri android init` completes | ⬜ | From `mobile/android/shell/` |
| Java 17 present | ✅ | Oracle JDK 17.0.2 |
| Gradle wrapper fetched | ⬜ | First `./gradlew tasks` run |

**Phase 0 complete when:** `adb devices` shows running emulator AND `tauri android dev` compiles without error.

---

## Phase 1 — Tauri Android Shell

| Task | Status | Notes |
|------|--------|-------|
| `mobile/android/shell/` scaffolded | ⬜ | Adapted from `desktop/shell/` |
| `tauri.conf.json` updated for Android | ⬜ | identifier, icons, no externalBin |
| `lib.rs` stripped to shell-only (no sidecar spawn) | ⬜ | Sidecar replaced by in-process Py |
| `tauri android build --debug` succeeds | ⬜ | |
| APK installs on emulator | ⬜ | |
| WebView loads static "Loading..." page | ⬜ | Proves WebView works |

**Phase 1 complete when:** debug APK installs, WebView visible on emulator.

---

## Phase 2 — Python Runtime via Chaquopy

| Task | Status | Notes |
|------|--------|-------|
| Chaquopy plugin added to `build.gradle` | ⬜ | version 15.0+ |
| Python 3.11 selected in Chaquopy config | ⬜ | |
| `pip { install "frappe" }` block added | ⬜ | May need custom package list |
| Frappe dependency audit done | ⬜ | Strip MariaDB/Redis deps |
| `python { ... }` block points to `mobile/android/runtime/runner/` | ⬜ | |
| Gradle sync succeeds | ⬜ | |
| Python import smoke test in Activity | ⬜ | `import frappe` no exception |

**Phase 2 complete when:** `import frappe` runs inside the Android app without crashing.

---

## Phase 3 — In-Process Frappe Server

| Task | Status | Notes |
|------|--------|-------|
| `mobile/android/runtime/runner/server.py` written | ⬜ | Adapted from desktop |
| `mobile/android/runtime/runner/runtime_paths.py` written | ⬜ | Android data dirs |
| `mobile/android/runtime/runner/migration.py` written | ⬜ | Seed site copy logic |
| Frappe starts on port 8765 (background thread) | ⬜ | Via Chaquopy `Python.getModule()` |
| `GET /login` returns 200 from emulator browser | ⬜ | |
| WebView loads `http://127.0.0.1:8765/login` | ⬜ | |

**Phase 3 complete when:** Frappe login page visible inside the app WebView.

---

## Phase 4 — Runtime Paths for Android

| Task | Status | Notes |
|------|--------|-------|
| `runtime_paths.py` uses `getFilesDir()` path | ⬜ | Via env var from Kotlin |
| `runtime_paths.py` uses `getExternalFilesDir()` for backups | ⬜ | |
| Seed site bundled in APK assets | ⬜ | Via Chaquopy `staticPython` or assets |
| Asset extraction on first run works | ⬜ | Copy assets → app data dir |
| SQLite DB created at correct path | ⬜ | |

**Phase 4 complete when:** SQLite DB created in correct Android app data dir, survives app restart.

---

## Phase 5 — First-Run Setup Screen

| Task | Status | Notes |
|------|--------|-------|
| `mobile/android/shell/src/setup.html` or Tauri frontend updated | ⬜ | |
| `get_setup_state` Tauri command works on Android | ⬜ | |
| `save_setup` Tauri command works on Android | ⬜ | |
| Config persisted in Android SharedPreferences or app data dir | ⬜ | |
| Server starts automatically after setup | ⬜ | |
| WebView transitions setup → login page | ⬜ | |

**Phase 5 complete when:** Fresh install → setup screen → Frappe login, no manual steps.

---

## Phase 6 — Smoke Test + PR

| Task | Status | Notes |
|------|--------|-------|
| Login with admin credentials works | ⬜ | |
| Desk loads (JS/CSS assets served) | ⬜ | |
| Create a simple DocType record | ⬜ | |
| SQLite integrity_check passes | ⬜ | |
| App survives backgrounding + resume | ⬜ | |
| Debug APK attached to PR | ⬜ | |
| PR opened: `feature/mobile-android-first-run` → `main` | ⬜ | |

**Phase 6 complete when:** PR open, all checklist items ticked.

---

_Last updated: (agent updates this after each phase)_
