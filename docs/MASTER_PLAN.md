# Frappe SQLite — Cross-Platform Master Plan

> How Frappe SQLite code is shared across Web, Desktop, Android, and iOS, and how platform deviations are handled.

---

## 1. Shared Core (`frappe/`)

One framework, four consumers. The entire `frappe/` directory (~55k commits of upstream history) is the shared core. It is identical across all platforms:

- **Desktop** — bundled into PyInstaller `_internal/`
- **Android** — symlinked into Chaquopy's Python path (`mobile/android/shell/src-tauri/gen/android/app/src/main/python/frappe`)
- **iOS** — copied into the app payload (`apps/frappe/`)
- **Web** (traditional bench) — installed via `bench get-app`

This is the biggest win — business logic, DocTypes, query builder, desk UI, etc. are completely shared.

---

## 2. Runtime Layer (platform-specific)

Each platform has its own `runtime/` that bootstraps Frappe. These are copy-paste adaptations of the same ideas:

| File | Desktop | Android | iOS | Deviation |
|------|---------|---------|-----|-----------|
| `main.py` | `argparse` + `webbrowser.open()` | Kotlin calls `main()` directly | `start_background()` from Swift | Entry point differs |
| `server.py` | `FRAPPE_SQLITE_DESKTOP=1` | Minimal env setup | Minimal env setup | Env flags differ |
| `runtime_paths.py` | `~/Library/Application Support/` | `FRAPPE_SQLITE_DATA_DIR` (filesDir) | `FRAPPE_DATA_DIR` (Documents/) | Path source differs |
| `migration.py` | `shutil.copytree` | Custom `_copytree` (no preserve perms) | `shutil.copytree` | Android read-only assets |

**How divergence is handled:** inline comments + environment variable injection from the native shell.

Example from Android `runtime_paths.py`:

```python
def app_data_root() -> Path:
    override = os.environ.get("FRAPPE_SQLITE_DATA_DIR")
    if override:
        return Path(override)
    # Fallback for local dev (not Android)
    return Path.home() / ".frappe-sqlite-mobile"
```

The native shell (Kotlin/Swift/Rust) sets these env vars before Python starts.

---

## 3. Shell Layer (native UI)

Completely separate per platform:

| Platform | Shell | WebView | Communication |
|----------|-------|---------|---------------|
| Desktop | Tauri v2 (Rust) | WebView | IPC → sidecar Python process |
| Android | Tauri v2 (Rust + Kotlin) | WebView | IPC → Chaquopy in-process Python |
| iOS | Briefcase/Swift | WKWebView | Direct Python C API (`PyRun_SimpleString`) |
| Web | Browser | Browser | HTTP to gunicorn/WSGI |

---

## 4. Shim Layer (missing dependencies)

Mobile cannot run Redis, MariaDB, RQ, psutil, etc. These are stubbed out:

```
mobile/android/shell/src-tauri/gen/android/app/src/main/python/
├── redis/          → no-op Redis client
├── rq/             → no-op Queue/Worker
├── psutil.py       → empty module
├── PIL.py          → empty module
├── nh3.py          → empty module
└── orjson.py       → empty module
```

Same pattern in `mobile/ios/poc/src/shims/`.

**How it works:** Frappe core imports `redis`, gets the shim. The shim satisfies the import but does nothing. Frappe's SQLite patches already disable the code paths that would actually call Redis (e.g., `NO_REDIS=1`).

---

## 5. Deviation Summary

| Aspect | Shared? | Notes |
|--------|---------|-------|
| Frappe framework (`frappe/`) | ✅ 100% | Same code, different bundling |
| Database layer | ✅ ~95% | SQLite patches shared; WAL mode everywhere |
| Runtime bootstrap | ⚠️ ~60% | Same structure, copy-pasted with tweaks |
| Asset handling | ⚠️ ~50% | Desktop symlinks, Android copies, iOS copies |
| Native shell | ❌ 0% | Completely different per platform |
| Shims | ❌ 0% | Duplicated Android/iOS (same content, diff paths) |

**The real duplication:** `runtime_paths.py`, `server.py`, `migration.py`, and the shims are essentially the same file copied 3× with path/env changes. This is technical debt — ideally these would live in a shared `frappe/runtime/` package with platform detectors.

---

## 6. Unification Roadmap

### Short term (current)
- Keep `frappe/` as the single shared core.
- Keep per-platform `runtime/` folders for paths and entry points.
- Accept shim duplication (it is small).

### Medium term
- Extract a shared `frappe/runtime/` package.
- Use `sys.platform` / env var detection instead of copy-paste:
  ```python
  if sys.platform == "darwin" and os.environ.get("FRAPPE_MOBILE"):
      # iOS paths
  elif os.environ.get("FRAPPE_ANDROID"):
      # Android paths
  else:
      # Desktop paths
  ```
- Single `runtime_paths.py`, single `migration.py`, single `server.py`.

### Long term
- Same runtime package consumed by all platforms.
- Platform-specific shells become thin wrappers.
- Shims become optional extras (`pip install frappe[android-shims]`).

---

## 7. Branch Ownership

| Branch | Purpose |
|--------|---------|
| `main` | Old orphan (stable base). PR #8 valid here. |
| `main-unified` | Unified Frappe + Android + iOS history. Target for mobile PRs. |
| `base/frappe-sqlite-v16` | Upstream Frappe v16 hotfix + SQLite phase-1 fixes. Reference base. |
| `feature/local-lifecycle-functions` | Desktop lifecycle (3 commits, unstable). |
| `feature/mobile-android-runnable` | Android Tauri shell. |
| `feature/mobile-ios-runnable` | iOS Briefcase shell. |
| `backup-old-main` | Safety backup of old orphan `main`. |
