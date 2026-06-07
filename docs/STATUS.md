# STATUS

Last updated: 2026-06-07T01:50Z by Kimi

## Current Phase
Phase 3 — Smoke test PASSED. Ready for Phase 4 (Tauri) or can ship as PyInstaller binary.

## Context
- Bench (host): `/Users/safwan/Code/docker/fdocker/development/sqlitepoc`
- Container: `devcontainer-frappe-1` (bind mount, files shared)
- Site: `sqliteonly.localhost`
- Apps: `frappe` only
- Host Python: 3.14.3
- Host venv: `.venv-macos`
- Binary: `dist/frappe-sqlite-macos/frappe-sqlite` (≈32MB executable + dependencies)

## Working
- ✅ bench serve works in Docker
- ✅ Python source runner works on host
- ✅ PyInstaller build succeeds on host
- ✅ Binary starts without Python installed
- ✅ HTTP 200 on login page
- ✅ Administrator login via API
- ✅ Fresh data directory auto-seeded from bundled seed site
- ✅ Data persists after kill + restart (ToDo created, found in DB after restart)
- ✅ No MariaDB required
- ✅ No Redis required
- ✅ Binds 127.0.0.1 only

## Broken / Unknown
- Phase 4 (Tauri shell) not started
- Phase 5 (signing, notarization, updater) deferred per plan
- No second-user-account test performed

## Key Adaptations from Original Plan
| Plan Assumption | Actual |
|---|---|
| Site: `site1.local` | `sqliteonly.localhost` |
| Apps: `frappe` + `erpnext` | `frappe` only |
| Product: `ERPNextSQLite` | `FrappeSQLite` |
| Bench root in container: `/workspaces/frappe-bench` | `/workspace/development/sqlitepoc` |
| Assets at `sites/assets/` | Need `assets -> sites/assets` symlink for dev mode |
| Log files | `FRAPPE_STREAM_LOGGING=1` avoids path issues |
| `apps.txt` in seed | Added to migration.py and build script |

## Next Action
User decision: proceed to Phase 4 (Tauri) or declare MVP complete with PyInstaller binary.
