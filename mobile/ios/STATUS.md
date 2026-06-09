# iOS Build Status

> Updated: 2026-06-09
> Branch: `feature/mobile-ios-runnable`

## Summary

The iOS app **builds, installs, and launches** in the iPhone 16 Pro simulator. The native WKWebView loads and connects to the embedded Frappe server. However, two blocking issues prevent full functionality:

1. **"Page not found" on launch** — The WKWebView shows Frappe's 404 page instead of the login page. This suggests the site seeding or routing is not fully working after a fresh install.

2. **Stale `frappe/` code loading** — The SQLite date converter fix (already working on Android) is present in the bundled `frappe/database/sqlite/database.py`, but the running app produces tracebacks showing the *old* pre-fix lambda code (`line 136, in <lambda>`). Despite verifying the built app bundle contains the fixed code, the runtime behaves as if it's executing an older version. This causes the ToDo list API to crash with `ValueError: Invalid isoformat string`.

## What Works ✅

- **Xcode build** — `xcodebuild` succeeds (Debug, iphonesimulator)
- **App install** — `xcrun simctl install` works
- **App launch** — App starts, Python 3.13 interpreter initializes, server thread starts
- **WKWebView** — Native UI loads and makes HTTP requests to `127.0.0.1:8765`
- **Login API** — `/api/method/login` returns a valid session cookie
- **Shared `frappe/` code** — The Android SQLite fixes are present in the source tree

## Active Blockers 🔴

| Issue | Symptom | Root Cause (Investigated) |
|---|---|---|
| **#1: Page not found** | WKWebView shows "Page not found" with "Back to Home" button | Site seeding may be incomplete after uninstall/reinstall cycle; or Frappe routing is misconfigured for the `sqliteonly.localhost` site |
| **#2: Stale code execution** | ToDo list API crashes with old lambda traceback despite fixed source | Unknown. Verified: no `.pyc` files, no `__pycache__`, no duplicate `frappe` packages. The built app bundle's `database.py` has `_parse_d`, but runtime traceback shows `<lambda>` at line 136. Hypotheses: (a) Xcode resource copying caching old files, (b) iOS app container delta-install keeping old code, (c) Python 3.13 iOS runtime has unusual bytecode caching |

## Build Info

- **Build tool:** Direct `xcodebuild` (Briefcase `create` used for initial scaffold only)
- **Workaround applied:** `Images.xcassets` removed from `PBXResourcesBuildPhase` to avoid CoreSimulator crash
- **Bundle ID:** `com.frappe.sqlite-ios.frappe-ios`
- **App size:** ~222MB (Debug, includes full `frappe/` + `runtime/` + wheels)
- **Device:** iPhone 16 Pro simulator (`0768629E-9A19-4915-8F42-2B51D0D0B046`)

## Key Files

| File | Purpose |
|---|---|
| `mobile/ios/poc/pyproject.toml` | Briefcase config |
| `mobile/ios/poc/src/frappe_ios/app.py` | Briefcase Python entrypoint |
| `mobile/ios/runtime/ios_main.py` | iOS server bootstrap (daemon thread) |
| `mobile/ios/runtime/server.py` | Werkzeug wrapper |
| `mobile/ios/runtime/migration.py` | Seed site + SQLite init |
| `mobile/ios/poc/build/.../AppDelegate.m` | WKWebView native shell |
| `mobile/ios/poc/build/.../main.m` | Python interpreter init + `UIApplicationMain` |

## Next Steps (When Resuming)

1. **Fix site seeding** — Debug why `run_migrations_if_needed()` produces a site that serves "Page not found" instead of the login page. Check `sites_path()`, `common_site_config.json`, and asset availability.
2. **Fix stale code loading** — Investigate Xcode's resource copy phase more deeply. Try forcing a full clean of `DerivedData`, `build/`, and the simulator app container. Consider modifying `database.py` to add an obvious runtime marker to definitively prove which code is executing.
3. **Test ToDo list** — Once the above two issues are resolved, verify the ToDo list loads without the `ValueError`.

## Pin Log

| Item | Version | Source |
|---|---|---|
| Python (host) | 3.13.3 | Homebrew |
| Python (embedded) | 3.13-b13 | BeeWare Python-Apple-support |
| Xcode | 18.2 | App Store |
| iOS SDK | 18.3 | Xcode bundled |
| briefcase | 0.4.2 | pip |
