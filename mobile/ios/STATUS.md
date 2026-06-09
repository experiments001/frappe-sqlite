# iOS Build Status

> Live progress tracker. Updated after every meaningful change.
> **Session paused.** Next: briefcase create retry after bulk shim fixes.

## Current Phase

**Phase 4 — Briefcase Shell (E1-E5)**

## Completed ✅

### Phase 0 — Research & Audit
- [x] A1: Runner audit — server.py fully reusable (no subprocess, 127.0.0.1 only)
- [x] A2: Dependency audit — 51 packages in trimmed requirements.txt
- [x] A3: Python-Apple-support — downloaded `Python-3.13-iOS-support.b13.tar.gz`
- [x] A4: Native shim audit — 18 shim files created (reused from Android)

### Phase 1 — Infrastructure
- [x] B1: Branch `feature/mobile-ios-first-run` created from `feature/mobile-android-first-run`
- [x] B2: Directory layout `mobile/ios/` created
- [x] B3: Trimmed `requirements.txt` created (51 packages)
- [x] B4: Build scripts created (`build_wheels_ios.sh`, `assemble_payload.sh`, `run_simulator.sh`, `run_device.sh`)

### Phase 2 — Runtime
- [x] C1: `ios_main.py` — in-process entrypoint with `start()` and `start_background()`
- [x] C2: `runtime_paths.py` — iOS sandbox `Documents/` paths
- [x] C3: `migration.py` — seed site copy + SQLite DB init on first run
- [x] C4: `server.py` — iOS wrapper (copied from desktop, no changes to shared logic)

### Phase 3 — Wheelhouse & Shims
- [x] D1: briefcase + cibuildwheel installed in `.venv`
- [x] D2: `Python.xcframework` downloaded to `vendor/`
- [x] D4: Native shims created (25+ shim files across `src/shims/` and `src/frappe_ios/shims/`)

### Phase 4 — Briefcase Config
- [x] E1: `pyproject.toml` created with iOS target config
- [x] E2: App config iterated to match Briefcase validation (`sources` must include module name)
- [x] E3: `app.py` bootstrap created with runtime sys.path setup

### Phase 6 — Documentation
- [x] G1: `AGENTS.md` updated with iOS section
- [x] G2: `CORE_CHANGES.md` updated with iOS additions
- [x] G3: `README.md` and `STATUS.md` created

## In Progress 🔄

- [ ] E4/E5: `briefcase create iOS` — iterating on dependency resolution
  - PyYAML: fixed with pure-Python wheel in `vendor/wheelhouse/`
  - cryptography/MarkupSafe/pyOpenSSL: removed from requirements, shims created
  - Next: retry briefcase create to find remaining issues

## Pending ⏳

### Phase 4 (continued)
- [ ] E4: `briefcase create iOS` — retry after bulk fixes
- [ ] E5: `briefcase build iOS`
- [ ] E6: `briefcase run iOS` (simulator)

### Phase 5 — WebView Integration
- [ ] F1: Add WKWebView + health-check polling
- [ ] F2: Test login page renders
- [ ] F3: Test create/persist data

### Phase 7 — Deferred
- [ ] H1: Xcode hand-built shell (Lane B)
- [ ] H2: Device wheels (`arm64_iphoneos`)
- [ ] H3: TestFlight / App Store prep

## Briefcase Config Iteration Log

| Attempt | Issue | Fix |
|---|---|---|
| v1 | `license.file` missing | Created LICENSE file |
| v2 | `sources` doesn't include package `frappeios` | Renamed app → `frappe_ios` |
| v3 | `sources` doesn't include package `frappe_ios` | Fixed sources to `src/frappe_ios` + `src/shims` |
| v4 | PyQRCode no iOS wheel | Removed from requirements + shim |
| v5 | Build dir exists (interactive prompt) | Added `--no-input` flag |
| v6 | PyYAML no iOS wheel | Built pure-Python wheel in vendor/wheelhouse |
| v7 | PyYAML still not found | Set `PIP_FIND_LINKS` env var |
| v8 | cryptography no iOS wheel | **Bulk fix:** removed cryptography/MarkupSafe/pyOpenSSL + shims |

## Key Technical Decisions

1. **In-process Python**: iOS bans subprocesses. `ios_main.py` runs Werkzeug on a daemon thread.
2. **Shared core**: Zero modifications to `frappe/`. iOS reuses Android-patched core.
3. **Native shims**: 25+ pure-Python stubs shadow missing packages (orjson, nh3, PIL, psutil, redis, rq, PyQRCode, markupsafe, cryptography, OpenSSL).
4. **Wheelhouse strategy**: Pure-Python packages work via PyPI. C extensions without iOS wheels are either shimmed or replaced with pure-Python builds.

## Next Steps (when resuming)

```bash
cd mobile/ios/poc
source ../.venv/bin/activate
export PIP_FIND_LINKS=/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-android/mobile/ios/vendor/wheelhouse
rm -rf build iOS
briefcase create iOS --no-input
```

Then iterate on any remaining dependency failures.

## Pin Log

| Item | Version | Source |
|---|---|---|
| Python (host) | 3.13.3 | Homebrew |
| Python (embedded) | 3.13-b13 | BeeWare Python-Apple-support |
| Xcode | 16.x | App Store |
| iOS SDK | 18.2 | Xcode bundled |
| briefcase | 0.4.2 | pip |
