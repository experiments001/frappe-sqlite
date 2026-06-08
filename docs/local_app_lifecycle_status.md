# Local App Lifecycle Status

Branch: `feature/local-lifecycle-functions`

Repo path: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-lifecycle`

## Runtime Inspection

| Capability | Status | File references | Notes |
| --- | --- | --- | --- |
| SQLite database backend | Working | `frappe/database/sqlite/database.py`, `frappe/database/sqlite/schema.py`, `frappe/database/sqlite/setup_db.py` | Existing adapter supports the local SQLite runtime and WAL-at-create behavior. |
| Desktop seed-site bootstrap | Partially working | `desktop/runtime/runner/migration.py`, `desktop/runtime/runner/runtime_paths.py` | Runtime copies a seed site into `~/Library/Application Support/FrappeSQLite/sites` when missing. It does not yet create arbitrary fresh Frappe sites from scratch. |
| Site config for local runtime | Working | `desktop/runtime/runner/server.py`, `frappe/desktop/_utils.py` | Runtime sets `SITES_PATH`, `FRAPPE_SITES_PATH`, `NO_REDIS`, `NO_MARIADB`; new helpers apply SQLite/local/sync/noop settings into `site_config.json`. |
| Migration from desktop runner | Partially working | `desktop/runtime/runner/main.py`, `desktop/runtime/runner/migration.py`, `frappe/desktop/migrate.py` | Existing runner only ensures seed availability. New helper exposes `migrate_site()` and `migrate_all_sites()` using Frappe `SiteMigration`. |
| App install/uninstall | Partially working | `frappe/installer.py`, `frappe/desktop/app_manager.py` | New helper distinguishes available apps in `sites/apps.txt` from site-installed apps. Simple names resolve to `https://github.com/frappe/<app>.git`; full Git URLs/local paths still work. Install delegates to Frappe installer; uninstall is intentionally minimal for PoC and updates config before migration. |
| Desktop build | Working wrapper / generated outputs absent | `desktop/scripts/build-sidecar.sh`, `desktop/scripts/build-app.sh`, `frappe/desktop/build.py` | New helper wraps existing sidecar and Tauri build scripts and exposes rebuild-needed checks. The repo does not track generated `_internal/` or `.app` outputs. |
| Full backup system | Missing by design | n/a | Out of scope for this phase. `export_site()`/`import_site()` provide portable archive primitives only. |
| Persistent desktop registry | Missing by design | n/a | Out of scope for this phase. Current discovery is filesystem-based. |
| Admin UI / marketplace / polished CLI | Missing by design | n/a | Out of scope. Minimal `python -m frappe.desktop.*` entry points are present for development testing. |

## Implemented in This Branch

- `frappe/desktop/site_manager.py`
  - `list_sites()`
  - `create_site()`
  - `remove_site()`
  - `drop_site()`
  - `clone_site()`
  - `export_site()`
  - `import_site()`
- `frappe/desktop/app_manager.py`
  - `resolve_app_source()`
  - `list_apps()`
  - `add_app()`
  - `install_app()`
  - `uninstall_app()`
  - `update_app()`
  - `remove_app()`
- `frappe/desktop/migrate.py`
  - `migrate_site()`
  - `migrate_all_sites()`
  - `check_site_needs_migration()`
- `frappe/desktop/build.py`
  - `build_desktop_app()`
  - `rebuild_desktop_app()`
  - `check_rebuild_needed()`
- `frappe/desktop/tests/test_site_manager.py`
  - smoke test for create/list/clone/export/import/remove with SQLite integrity check.

## Known Limitations

- `create_site()` creates the site directory, local config, and a SQLite database copied from `frappe/database/sqlite/framework_sqlite.db` by default. It also has an opt-in `use_frappe_installer=True` path to run Frappe's full SQLite `new-site` installer, and `complete_setup=True` to run setup wizard completion with first-run fields such as timezone/country/currency/language/admin user information. The desktop UI can collect those fields and call this function.
- `uninstall_app()` is intentionally conservative and config-driven for the PoC. A full implementation should delegate to the framework uninstall path and handle module cleanup, hooks, scheduled jobs, fixtures, and orphaned DocTypes.
- `check_site_needs_migration()` is best-effort and currently uses the presence of `touched_tables.json` as a weak signal.
- `build_desktop_app()` wraps existing scripts; it does not introduce a persistent build profile registry.
- Generated desktop outputs such as PyInstaller `_internal/` and the Tauri `.app` bundle are intentionally not committed. A release build must run the existing sidecar/app build scripts and verify bundle freshness.

## Latest Verification

Validated on 2026-06-08 from `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-lifecycle` using `/Users/safwan/Code/docker/fdocker/development/sqlitepoc/.venv-macos/bin/python`:

- Lightweight site lifecycle smoke: create/list/clone/export/import/remove passed with SQLite `integrity_check` = `ok`.
- Frappe-like `drop_site()` archive semantics passed.
- App source resolver passed for simple names (`crm`, `erpnext`) and GitHub slugs.
- Full SQLite new-site path passed with `use_frappe_installer=True`.
- Full SQLite new-site plus setup wizard completion passed with `complete_setup=True`, timezone `Asia/Dubai`, country `United Arab Emirates`, currency `AED`, language `English`, and admin password set.
