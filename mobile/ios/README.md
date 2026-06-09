# Frappe SQLite — iOS App

> iOS shell for the Frappe SQLite POC. Shares the same `frappe/` core as desktop and Android.

## Architecture

```
frappe/                    ← shared core (same as desktop + Android)
  ├──► desktop/runtime/    ← PyInstaller sidecar (macOS)
  ├──► mobile/android/     ← Chaquopy (Android)
  └──► mobile/ios/         ← Python-Apple-support + Briefcase (iOS) ← YOU ARE HERE
```

iOS is the **same Frappe + SQLite runtime** with two differences:
1. **Python runs in-process** (iOS bans subprocesses) — handled by `ios_main.py`
2. **iOS sandbox paths** — writable data in `Documents/`, bundled payload read-only

## Directory Layout

```
mobile/ios/
  README.md           ← this file
  STATUS.md           ← live progress tracker
  poc/                ← Lane A: Briefcase-generated PoC app
    pyproject.toml    ← briefcase config (iOS target)
    src/frappe_ios/
      app.py          ← thin bootstrap → calls shared runner
      shims/          ← pure-Python stubs (orjson, nh3, redis, rq, PIL, psutil)
  shell/              ← Lane B: hand-built Xcode project (deferred)
    FrappeSQLite/
      AppDelegate.swift
      WebViewController.swift
      PythonRunner.swift
  runtime/            ← iOS-specific Python runtime
    ios_main.py       ← in-process entrypoint
    runtime_paths.py  ← iOS sandbox paths
    migration.py      ← seed site + first-run logic
    server.py         ← Werkzeug wrapper (reuses desktop logic)
  vendor/             ← git-lfs managed binaries
    Python.xcframework  ← BeeWare Python-Apple-support 3.13
    wheelhouse/         ← iOS wheels (*.whl)
  scripts/
    build_wheels_ios.sh   ← cibuildwheel driver
    assemble_payload.sh   ← collect frappe/ + sites + seed + wheels
    run_simulator.sh      ← briefcase create/build/run for Simulator
    run_device.sh         ← briefcase build/run for connected device
```

## Quick Start (PoC — Lane A)

### Prerequisites
- macOS 14+ with Apple Silicon
- Xcode 16+ (`xcode-select --install`)
- Python 3.13 (`brew install python@3.13`)
- Rust (`rustup target add aarch64-apple-ios aarch64-apple-ios-sim`)

### 1. Install tools
```bash
cd mobile/ios
python3.13 -m venv .venv
source .venv/bin/activate
pip install briefcase cibuildwheel
```

### 2. Download Python runtime (already in `vendor/`)
```bash
ls vendor/Python.xcframework  # pre-downloaded Python-3.13-iOS-support.b13
```

### 3. Build & run on Simulator
```bash
cd poc
briefcase create iOS
briefcase build iOS
briefcase run iOS
```

### 4. Test
- App launches → splash → Frappe login page
- Log in as `Administrator` / `admin`
- Create a ToDo or Customer
- Kill app → relaunch → data persists

## Native Shims

Packages that don't have iOS wheels are stubbed with pure-Python fallbacks:

| Package | Shim | Why |
|---|---|---|
| orjson | `shims/orjson.py` | Rust JSON — wraps stdlib `json` |
| nh3 | `shims/nh3.py` | Rust HTML sanitizer — uses `html.escape` |
| PIL | `shims/PIL.py` | C imaging — no-op Image class |
| psutil | `shims/psutil.py` | C system info — minimal fallback |
| redis | `shims/redis/` | No Redis server on device |
| rq | `shims/rq/` | Depends on redis |

## Key Differences from Desktop/Android

| Aspect | Desktop | Android | iOS |
|---|---|---|---|
| Python | Host 3.12+ | Chaquopy 3.11 | Embedded 3.13 (Python-Apple-support) |
| Launch | subprocess sidecar | Kotlin thread | Swift thread / Briefcase daemon |
| Bundle | PyInstaller | APK assets | App bundle + `.xcframework` |
| Paths | `~/Library/...` | `/data/data/.../files/` | `Documents/` sandbox |
| Shims | None | APK `python/` dir | `shims/` package |

## Lane B (Hand-Built Shell)

For full control (post-PoC), see `shell/` and the plan document.
The hand-built shell uses:
- `Python.xcframework` embedded & signed
- `PythonRunner.swift` — starts interpreter in-process
- `WebViewController.swift` — WKWebView + health-check polling

## See Also

- Build plan: `docs/ios/MOBILE_IOS_BUILD_PLAN.md` (in Codex)
- Android implementation: `mobile/android/`
- Desktop implementation: `desktop/`
- Core changes: `CORE_CHANGES.md`
