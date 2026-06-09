# Core Changes Catalog — Frappe SQLite on Android

> Branch: `feature/mobile-android-first-run`  
> Target: Python 3.11 + Chaquopy + SQLite (no MariaDB, no Redis, no Docker)

This document catalogs every modification made to the Frappe framework source to run on Android via Chaquopy, with an assessment of whether each change is suitable for upstream contribution.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| 🟢 **Upstream** | Safe, valuable improvement for mainline Frappe |
| 🟡 **Discuss** | Could upstream with discussion; may need refinement |
| 🔴 **Fork-only** | Android/Chaquopy/SQLite-specific; not suitable for upstream |

---

## 1. Python 3.11 Syntax Backports

Frappe upstream uses Python 3.12+ syntax (PEP 695 `type` aliases, union `X \| Y`, `typing.override`). Chaquopy ships Python 3.11. These changes restore 3.11 compatibility.

### 1.1 PEP 695 `type X =` → `X =` assignment

**Files:**
- `frappe/__init__.py` — `ConfType`, `SessionType`, `LogMessageType`, `JobMetaType`, `ResponseDict`, `FlagsDict`, `FormDict`
- `frappe/model/document.py` — `_SingleDocument`, `_NewDocument`
- `frappe/types/filter.py` — `Doct`, `Fld`, `Op`, `DateTime`, `_Value`, `_InputValue`, `Value`, `InputValue`, `FilterSignature`
- `frappe/desk/doctype/event/event.py` — `EventLikeDict`

**Diff pattern:**
```python
# Before (3.12+)
type EventLikeDict = Event | frappe._dict
# After (3.11)
EventLikeDict = Event | frappe._dict
```

**Why:** Python 3.11 does not support `type` statement (PEP 695). Syntax error on import.

**Verdict:** 🔴 **Fork-only** — Upstream intentionally targets 3.12+. Backporting would regress their type-checking story.

---

### 1.2 Union syntax `X | Y` → `Optional[X] / Union[X, Y]`

**Files:**
- `frappe/__init__.py` — `cache`, `client_cache`, `db`, `qb`, `get_precision()`
- `frappe/utils/data.py` — `md_to_html()`, `markdown()`
- `frappe/utils/local.py` — `LocalProxy[T]` generic syntax
- `frappe/utils/typing_validations.py` — `ForwardRefOrStr`, `apply_condition`, `current_exception`
- `frappe/model/document.py` — `update_child_table()`, `new_doc()`
- `frappe/model/naming.py` — `is_autoincremented()`, `parse_naming_series()`
- `frappe/model/delete_doc.py` — (type hints in function signatures)
- `frappe/query_builder/custom.py` — `GROUP_CONCAT`, `STRING_AGG`, `ConstantColumn`
- `frappe/query_builder/terms.py` — `ParameterizedValueWrapper`, `SubQuery`
- `frappe/query_builder/utils.py` — `get_query_builder()`, `mask_fields()`
- `frappe/deferred_insert.py` — `deferred_insert()`, `insert_record()`
- `frappe/core/doctype/doctype/doctype.py` — `validate_autoincrement_autoname()`
- `frappe/core/doctype/file/utils.py` — `get_extension()`, `find_file_by_url()`
- `frappe/website/doctype/website_theme/website_theme.py` — `get_active_theme()`
- `frappe/www/printview.py` — `get_print_format_doc()`, `get_rendered_template()`, `set_title_values...()`, `get_print_style()`, `get_font()`
- `mobile/android/runtime/runner/server.py` — `serve()`

**Diff pattern:**
```python
# Before
def get_precision(doctype: str, fieldname: str, currency: str | None = None) -> int:
# After
def get_precision(doctype: str, fieldname: str, currency: Optional[str] = None) -> int:
```

**Why:** Python 3.11 does not accept `X | Y` in all typing contexts (PEP 604). `from __future__ import annotations` defers evaluation, but runtime introspection (e.g. `get_type_hints`) still fails in some paths.

**Verdict:** 🔴 **Fork-only** — Same as above; upstream is 3.12+.

---

### 1.3 `typing.override` → `typing_extensions.override`

**Files:**
- `frappe/model/document.py`
- `frappe/types/filter.py`
- `frappe/types/frappedict.py`

**Diff pattern:**
```python
# Before
from typing import override
# After
from typing_extensions import override
```

**Why:** `typing.override` was added in Python 3.12.

**Verdict:** 🟢 **Upstream** — Using `typing_extensions` instead of `typing` for `@override` is a common compatibility pattern. Could be accepted as a small cleanup PR since `typing_extensions` is already a dependency.

---

### 1.4 `except A, B:` → `except (A, B):`

**Files:**
- `frappe/desk/reportview.py` — `get_stats()`
- `frappe/model/delete_doc.py` — `delete_doc()` (two occurrences)

**Diff pattern:**
```python
# Before (invalid in 3.11 — actually a Python 2 holdover that only works in 3.12+)
except frappe.db.InternalError, frappe.db.ProgrammingError:
# After
except (frappe.db.InternalError, frappe.db.ProgrammingError):
```

**Why:** The comma syntax in `except` is a Python 2 leftover. It happens to parse in 3.12 but may not in 3.11 depending on parser state. The tuple form is correct in all versions.

**Verdict:** 🟢 **Upstream** — This is a **bug fix**. The comma form catches only the first exception and binds the second to a variable name. This is almost certainly unintended behavior. Worth a standalone PR.

---

### 1.5 `LocalProxy[T]` generic → `class LocalProxy(WerkzeugLocalProxy, Generic[T])`

**File:** `frappe/utils/local.py`

**Diff pattern:**
```python
# Before
class LocalProxy[T](WerkzeugLocalProxy):
# After
class LocalProxy(WerkzeugLocalProxy, Generic[T]):
```

**Why:** Python 3.11 generics use `typing.Generic` base class, not subscriptable class syntax.

**Verdict:** 🔴 **Fork-only** — 3.12+ syntax.

---

## 2. SQLite Compatibility Fixes

### 2.1 Timestamp converter: `fromisoformat` space separator

**File:** `frappe/database/sqlite/database.py`

**Diff:**
```python
# Before
sqlite3.register_converter("timestamp", lambda x: datetime.fromisoformat(x.decode()))
# After
def _parse_ts(x):
    s = x.decode()
    if " " in s and "T" not in s:
        s = s.replace(" ", "T", 1)
    return datetime.fromisoformat(s)
sqlite3.register_converter("timestamp", _parse_ts)
```

**Why:** SQLite stores timestamps as `YYYY-MM-DD HH:MM:SS.ffffff` (space separator). Python 3.11's `datetime.fromisoformat()` does **not** accept space separators — this was only added in 3.11.4+ or 3.12 depending on build. On Android Chaquopy 3.11 it crashes with `ValueError: Invalid isoformat string`.

**Verdict:** 🟢 **Upstream** — This is a **robustness improvement** that makes the SQLite backend work correctly on any Python version. It should not affect 3.12 behavior. PR-worthy.

---

## 3. Android / Embedded Runtime Fixes

### 3.1 `faulthandler.enable()` guard

**File:** `frappe/_optimizations.py`

**Diff:**
```python
try:
    faulthandler.enable()
    faulthandler.register(signal.SIGUSR1, file=sys.__stderr__)
except (OSError, io.UnsupportedOperation):
    # Android/chaquopy stderr has no fileno
    pass
```

**Why:** On Android, `sys.stderr` is a Chaquopy wrapper without a real file descriptor. `faulthandler.enable()` raises `UnsupportedOperation`.

**Verdict:** 🟢 **Upstream** — Safe defensive programming. `faulthandler` is best-effort anyway; silencing the error on platforms without proper stderr is harmless and correct.

---

### 3.2 Conditional MariaDB import via `NO_MARIADB`

**File:** `frappe/app.py`

**Diff:**
```python
if not os.environ.get("NO_MARIADB"):
    import frappe.database.mariadb.mysqlclient
```

**Why:** `mysqlclient` cannot be installed on Android (requires libmysqlclient C library). The import crashes at startup even when using SQLite.

**Verdict:** 🟡 **Discuss** — Frappe's architecture assumes MariaDB is always available. A cleaner upstream approach might be a try/except import or a settings-driven backend selection. An env var is pragmatic but maybe too ad-hoc for upstream. However, making the import lazy/conditional is generally good for reducing startup import graph.

---

### 3.3 `bundled_asset()` None-guard

**File:** `frappe/utils/jinja_globals.py`

**Diff:**
```python
# Before
path = bundled_assets.get(path) or path
# After
path = bundled_assets.get(path) or path if bundled_assets else path
```

**Why:** On Android, `get_assets_json()` can return `None` if `assets.json` is missing during early startup or asset extraction race conditions. This causes `AttributeError: 'NoneType' object has no attribute 'get'`.

**Verdict:** 🟢 **Upstream** — Defensive null-check. Harmless and prevents crashes in edge cases (e.g. missing assets during development, fresh installs).

---

### 3.4 `template_page.py` — `__import__()` fallback for AssetFinder

**File:** `frappe/website/page_renderers/template_page.py`

**Diff:** Added `else` branch after `os.path.exists()` check:
```python
else:
    candidate = self.app + "." + self.pymodule_path.replace(os.path.sep, ".")[:-3]
    try:
        __import__(candidate)
        self.pymodule_name = candidate
    except ImportError:
        pass
```

**Why:** Chaquopy's `AssetFinder` stores `.py` files inside the APK zip. `os.path.exists()` returns `False` for them, so Frappe skips page context modules (`login.py`, `desk.py`, etc.) and pages render without context. `__import__()` actually works because Python's import machinery uses the finder, not the filesystem.

**Verdict:** 🟡 **Discuss** — This is a valid portability fix for any environment where Python modules live in non-filesystem finders (zipapp, embedded, etc.). Upstream might accept it with a clearer comment. However, it slightly changes semantics: a missing file that is importable via some other path would now be accepted.

---

## 4. Pydantic v1 Compatibility

**File:** `frappe/utils/typing_validations.py`

**Changes:**
1. Removed `pydantic.ConfigDict`, `TypeAdapter`, `PydanticUserError`, `ValidationError` imports
2. Replaced with a `_SimpleTypeAdapter` shim that delegates to `BaseModel.parse_obj()` for v1
3. Changed `ConfigDict(...)` to plain dict `{"arbitrary_types_allowed": True}`
4. Widened exception catch from `PydanticValidationError` to generic `Exception`

**Why:** The pinned pydantic version on Android is `1.10.21` (v1 API). Frappe upstream uses pydantic v2 (`TypeAdapter`, `ConfigDict`, `ValidationError`).

**Verdict:** 🔴 **Fork-only** — Upstream has migrated to v2. This is a deliberate downgrade for Android pip constraints. Not upstreamable.

---

## 5. Native Module Shims (Android unavailable)

These are **new untracked files** placed in `mobile/android/shell/src-tauri/gen/android/app/src/main/python/` to shadow missing native packages.

### 5.1 `orjson.py`

**Why:** `orjson` is a Rust-native JSON serializer. No Android wheel available.

**Approach:** Wraps stdlib `json` module. `dumps()` returns `bytes` (matching orjson). Option flags are no-ops.

**Verdict:** 🔴 **Fork-only** — Shim, not a framework change.

### 5.2 `nh3.py`

**Why:** `nh3` (Ammonia HTML sanitizer) is Rust-native. No Android wheel.

**Approach:** `html.escape()` fallback. Recently expanded to accept all nh3 keyword args (`generic_attribute_prefixes`, `filter_style_properties`, etc.) so Frappe's `clean_html()` doesn't crash on unexpected kwargs.

**Verdict:** 🔴 **Fork-only** — Shim.

### 5.3 `psutil.py`

**Why:** `psutil` requires platform-specific C extensions for process info.

**Approach:** Stub `cpu_count()`, `Process` class with dummy `memory_info()`.

**Verdict:** 🔴 **Fork-only** — Shim.

### 5.4 `redis/` package

**Why:** No Redis server on Android; `redis-py` has native parsing extensions.

**Approach:** Minimal `Redis` and `StrictRedis` classes with no-op methods. Supports basic get/set/keys/locks/pubsub/pipeline patterns that Frappe calls during init.

**Verdict:** 🔴 **Fork-only** — Shim.

### 5.5 `rq/` package

**Why:** `rq` (Redis Queue) depends on Redis and is used for background jobs.

**Approach:** Stub `Queue`, `Worker`, `Callback`, `get_current_job()`.

**Verdict:** 🔴 **Fork-only** — Shim.

### 5.6 `PIL.py`

**Why:** Pillow requires compiled C libraries (libjpeg, libpng, etc.).

**Approach:** Minimal `Image`, `ImageOps`, `ExifTags` stubs with `__version__`.

**Verdict:** 🔴 **Fork-only** — Shim.

---

## 6. Android Runtime (New/Modified Files in `mobile/android/runtime/`)

These are **new infrastructure** for the Android app. They are not modifications to existing Frappe code.

### 6.1 `runner/main.py`

Entry point called from Kotlin via Chaquopy. Runs migrations, then starts Werkzeug server.

**Verdict:** 🔴 **Fork-only** — Android-specific orchestration.

### 6.2 `runner/server.py`

Werkzeug bootstrap for Android:
- Sets `FRAPPE_STREAM_LOGGING=1`
- Changes CWD to `sites_path()` (critical for `assets.json` discovery)
- Wraps `application_with_statics()` in try/except with stderr logging

**Verdict:** 🔴 **Fork-only** — Android-specific server startup.

### 6.3 `runner/migration.py`

First-run site initialization:
- `_copytree()` — copies without preserving permissions (Android read-only AssetFinder)
- `ensure_assets_available()` — copies `assets/` and `frappe/public` to `sites/assets/`
- `seed_site_if_missing()` — extracts pre-built seed site from APK assets, skips `install_app` if `.db` exists

**Verdict:** 🔴 **Fork-only** — Android-specific file management.

### 6.4 `runner/runtime_paths.py`

Path resolution using env vars injected by Kotlin (`FRAPPE_SQLITE_DATA_DIR`, `FRAPPE_SQLITE_BUNDLE_ROOT`).

**Verdict:** 🔴 **Fork-only** — Android-specific path layer.

---

## 7. Build / Gradle / Kotlin Changes

### 7.1 `chaquopy.gradle`

New file: Chaquopy plugin config with Python 3.11, 40+ pip packages, Android shims.

**Verdict:** 🔴 **Fork-only** — Android build config.

### 7.2 `MainActivity.kt`

Modified to:
- Start Chaquopy Python
- Inject env vars (`NO_REDIS=1`, `NO_MARIADB=1`, `FRAPPE_SQLITE_DESKTOP=1`)
- Extract `resources/seed_site` APK assets on first launch
- Spawn Python server in background thread
- Navigate WebView to `http://127.0.0.1:8765`

**Verdict:** 🔴 **Fork-only** — Android app shell.

### 7.3 `build.gradle.kts`, `settings.gradle`, `lib.rs`, `tauri.conf.json`

Tauri + Chaquopy build integration.

**Verdict:** 🔴 **Fork-only** — Android build plumbing.

---

## 8. Seed Site / Asset Bundle

`mobile/android/runtime/resources/seed_site/` (untracked) contains:
- Pre-built `sqliteonly.localhost` site with SQLite DB
- `site_config.json` (note: `maintenance_mode: 0` — was originally `1` which caused read-only mode)
- Built frontend assets (`assets.json`, CSS/JS bundles)

**Verdict:** 🔴 **Fork-only** — Build artifact / demo data.

---

## Summary Table

| # | Change | Files | Verdict | Notes |
|---|--------|-------|---------|-------|
| 1.1 | PEP 695 `type X =` → `X =` | 4 files | 🔴 Fork-only | 3.11 compat |
| 1.2 | Union `X \| Y` → `Optional/Union` | 17 files | 🔴 Fork-only | 3.11 compat |
| 1.3 | `typing.override` → `typing_extensions` | 3 files | 🟢 Upstream | Safe compat pattern |
| 1.4 | `except A, B:` → `except (A, B):` | 2 files | 🟢 Upstream | **Bug fix** — catches wrong exception |
| 1.5 | `LocalProxy[T]` generic syntax | 1 file | 🔴 Fork-only | 3.11 compat |
| 2.1 | SQLite timestamp space separator | `database/sqlite/database.py` | 🟢 Upstream | Robustness fix |
| 2.2 | SQLite date/time loose typing | `database/sqlite/database.py` | 🟢 Upstream | SQLite returns full datetime for date columns |
| 3.1 | `faulthandler` try/except | `_optimizations.py` | 🟢 Upstream | Defensive |
| 9.1 | `sessions.py` session_end parsing | `sessions.py` | 🟢 Upstream | Defensive |
| 9.2 | `security_settings.py` expires parsing | `security_settings.py` | 🟢 Upstream | Defensive |
| 9.3 | MainActivity server polling | `MainActivity.kt` | 🔴 Fork-only | Android UI orchestration |
| 3.2 | Conditional MariaDB import | `app.py` | 🟡 Discuss | Env var guard |
| 3.3 | `bundled_asset` None-guard | `jinja_globals.py` | 🟢 Upstream | Defensive |
| 3.4 | `template_page.py` import fallback | `template_page.py` | 🟡 Discuss | AssetFinder support |
| 4 | Pydantic v1 shim | `typing_validations.py` | 🔴 Fork-only | v1 vs v2 |
| 5.1–5.6 | Native module shims | `python/*.py` | 🔴 Fork-only | orjson, nh3, psutil, redis, rq, PIL |
| 6.1–6.4 | Android runtime | `mobile/android/runtime/` | 🔴 Fork-only | Server, migration, paths |
| 7 | Build / Kotlin / Gradle | `mobile/android/shell/` | 🔴 Fork-only | Tauri + Chaquopy integration |
| 8 | Seed site bundle | `resources/seed_site/` | 🔴 Fork-only | Pre-built demo data |

---

## Recommended Upstream PRs

If we want to contribute back to Frappe, these are the cleanest, most valuable PRs to extract:

### PR A: Fix `except A, B:` syntax bug
**Files:** `frappe/desk/reportview.py`, `frappe/model/delete_doc.py`

The comma syntax `except OSError, KeyError:` only catches `OSError` and binds `KeyError` as a variable name. It does **not** catch both exceptions. This is a genuine bug that happens to parse in 3.12 but has incorrect semantics.

### PR B: SQLite timestamp converter robustness
**File:** `frappe/database/sqlite/database.py`

Replace the naive `datetime.fromisoformat(x.decode())` with a helper that normalizes space-separated SQLite timestamps. Also handle SQLite's loose typing where `date` columns may contain full datetime strings (split on space) and `time` columns may also contain full datetimes. This makes the SQLite backend work on all Python versions and avoids crashes on legacy data.

### PR C: `faulthandler` defensive guard
**File:** `frappe/_optimizations.py`

Wrap `faulthandler.enable()` in `try/except (OSError, io.UnsupportedOperation)` so Frappe starts gracefully on platforms without real stderr (Android, some containers, Windows services).

### PR D: `bundled_asset` None-guard
**File:** `frappe/utils/jinja_globals.py`

One-line null-check to prevent `AttributeError` when `assets.json` is missing or unreadable.

### PR E: `typing_extensions.override` fallback
**Files:** `frappe/model/document.py`, `frappe/types/filter.py`, `frappe/types/frappedict.py`

Import `override` from `typing_extensions` with a fallback. This is a common pattern in libraries that support a range of Python versions.

---

## Notes for Maintainers

- **Do not upstream Python 3.11 syntax changes.** Frappe upstream has committed to 3.12+ and uses PEP 695/604 features intentionally. Our fork must carry these as a permanent patch set until Chaquopy supports 3.12+.
- **The `except A, B:` bug should definitely be reported.** It may cause silent failures in error handling on production sites.
- **The SQLite timestamp fix is the most obviously correct upstream change.** It has zero downside for 3.12 users and fixes a real data-format edge case.


---

## 9. Additional Fixes from Post-Build Verification (2025-06-09)

### 9.1 `sessions.py` — `session_end` timestamp parsing

**File:** `frappe/sessions.py:373`

**Diff:**
```python
# Before
and datetime.now(tz=UTC) > datetime.fromisoformat(session_end)
# After
and datetime.now(tz=UTC) > datetime.fromisoformat(
    session_end.replace(" ", "T", 1) if isinstance(session_end, str) and " " in session_end else session_end
)
```

**Why:** `session_end` values from SQLite session storage contain space-separated timestamps. `datetime.fromisoformat()` fails on Python 3.11 with spaces.

**Verdict:** 🟢 **Upstream** — Defensive handling of SQLite datetime formats. Same rationale as 2.1.

---

### 9.2 `security_settings.py` — `public_expires` timestamp parsing

**File:** `frappe/core/doctype/security_settings/security_settings.py:78,120`

**Diff pattern:**
```python
# Before
expires = datetime.fromisoformat(expires)
# After
expires = datetime.fromisoformat(expires.replace(" ", "T", 1) if " " in expires else expires)
```

**Why:** Same as 9.1 — SQLite returns space-separated datetimes for string fields.

**Verdict:** 🟢 **Upstream** — Same rationale as 2.1/9.1.

---

### 9.3 `MainActivity.kt` — Server-ready polling

**File:** `mobile/android/shell/src-tauri/gen/android/app/src/main/java/com/frappe/sqlite_mobile/MainActivity.kt`

**Change:** Replaced hardcoded `Handler.postDelayed({...}, 3000)` with a background thread that polls `127.0.0.1:8765` via `Socket.connect()` every 500ms until the server accepts connections, then navigates the WebView.

**Why:** The Python server takes 5–10 seconds to start on first launch (Chaquopy init + imports + DB setup). A fixed 3-second delay caused the WebView to hit `ERR_CONNECTION_REFUSED` and get stuck on the error page.

**Verdict:** 🔴 **Fork-only** — Android-specific UI orchestration.

---

## Known Issues (Not Our Bugs)

### ToDo form view title shows raw HTML

When opening a single ToDo document, the form view title bar shows raw HTML like `<div class="ql-editor read-mode"><p>Ok</p></div>` instead of just "Ok".

**Root cause:** Default Frappe behavior. `todo.json` sets `"title_field": "description"`. The `description` field is a `TextEditor` that stores HTML. `frappe/public/js/frappe/model/model.js:617` (`get_doc_title()`) returns `doc[meta.title_field]` raw without calling `strip_html()`.

**Our involvement:** None. This is upstream Frappe behavior. The list view DOES strip HTML (see `list_view.js:958`), but the form view title does not.


---

## iOS Additions (feature/mobile-ios-first-run)

> **Note:** iOS changes are entirely additive — no modifications to existing `frappe/` files.
> The iOS runtime reuses the same `frappe/` core, `desktop/runtime/runner/server.py` pattern,
> and SQLite backend already established for desktop and Android.

### i0. New Directory: `mobile/ios/`

All iOS-specific code lives under `mobile/ios/` and does not touch `frappe/`.

| File | Purpose | Reuses? |
|---|---|---|
| `mobile/ios/poc/pyproject.toml` | Briefcase iOS app configuration | ❌ New |
| `mobile/ios/poc/src/frappe_ios/app.py` | Briefcase entrypoint — starts server thread | ❌ New (thin wrapper) |
| `mobile/ios/poc/src/frappe_ios/__init__.py` | Package marker | ❌ New |
| `mobile/ios/poc/src/shims/` | 18 pure-Python stub files | 🟢 Reused from Android |
| `mobile/ios/runtime/ios_main.py` | In-process entrypoint (EMBEDDED_INPROCESS) | 🟡 Adapted from desktop |
| `mobile/ios/runtime/runtime_paths.py` | iOS sandbox Documents/ paths | 🟡 Adapted from Android |
| `mobile/ios/runtime/migration.py` | Seed site + SQLite init on first run | 🟡 Adapted from Android |
| `mobile/ios/runtime/server.py` | Werkzeug wrapper | 🟢 Copied from desktop |
| `mobile/ios/scripts/requirements.txt` | Trimmed 51-package runtime set | 🟡 Derived from pyproject.toml |
| `mobile/ios/scripts/build_wheels_ios.sh` | cibuildwheel driver | ❌ New |
| `mobile/ios/scripts/assemble_payload.sh` | Bundle assembly | ❌ New |
| `mobile/ios/scripts/run_simulator.sh` | Simulator runner | ❌ New |
| `mobile/ios/scripts/run_device.sh` | Device runner | ❌ New |
| `mobile/ios/vendor/Python.xcframework` | BeeWare Python-Apple-support 3.13 | ❌ Prebuilt binary |
| `mobile/ios/README.md` | iOS-specific documentation | ❌ New |
| `mobile/ios/STATUS.md` | Live progress tracker | ❌ New |

### i1. Architecture Decision: In-Process Python

**File:** `mobile/ios/runtime/ios_main.py`

iOS bans subprocesses. Unlike desktop (PyInstaller sidecar spawned by Tauri) and
Android (Chaquopy runs Python in a background thread from Kotlin), iOS runs Python
**in-process** on a `DispatchQueue`/`Thread`:

```python
# ios_main.py
import ios_main
ios_main.start_background()  # daemon thread → Werkzeug serves in-process
```

**Verdict:** 🔴 **Fork-only** — iOS-specific constraint.

### i2. Native Shims (Reused from Android)

**Files:** `mobile/ios/poc/src/shims/*`

Same 18 pure-Python stubs as Android:
- `orjson.py` — wraps `json`
- `nh3.py` — uses `html.escape`
- `PIL.py` — no-op Image class
- `psutil.py` — minimal system info fallback
- `redis/` — no-op Redis client package
- `rq/` — no-op RQ queue package

**Verdict:** 🟢 **Reused verbatim** from Android. No changes needed.

### i3. Wheelhouse Strategy

iOS wheels are built with `cibuildwheel` targeting `arm64_iphonesimulator` (Sim)
and `arm64_iphoneos` (device). Heavy Rust/C deps (cryptography, pydantic-core)
may fail; the trimmed requirements drop non-critical deps and stub the rest.

**Verdict:** 🔴 **Fork-only** — iOS packaging concern.

### i4. No `frappe/` Modifications

Unlike Android (which patched `database/sqlite/database.py`, `sessions.py`,
`security_settings.py` for `fromisoformat` issues), iOS reuses the already-patched
`frappe/` tree from `feature/mobile-android-first-run`.

**Verdict:** 🟢 **Zero new core changes** — iOS is a pure consumer of the shared runtime.

---

## Summary: Cross-Platform Change Surface

| Platform | Files Added | Files Modified in `frappe/` | Shared Core Reused? |
|---|---|---|---|
| Desktop | ~15 in `desktop/` | 0 (adds runner, doesn't modify core) | ✅ |
| Android | ~20 in `mobile/android/` | ~5 (fromisoformat fixes, compat shims) | ✅ (after patches) |
| iOS | ~25 in `mobile/ios/` | **0** | ✅ (reuses Android-patched core) |

The iOS implementation is the thinnest platform layer yet — it adds only
infrastructure (Briefcase config, shell scripts, shim copies) and no modifications
to the shared `frappe/` framework.
