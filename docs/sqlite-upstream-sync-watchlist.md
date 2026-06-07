# SQLite Upstream Sync Watchlist

Date: 2026-06-08

## Purpose

This repository should remain a Frappe-shaped fork. SQLite support is an optional runtime profile, not a restructuring of Frappe.

The goal during future upstream syncs is:

- keep MariaDB/PostgreSQL behavior unchanged by default,
- keep SQLite selected through site config or environment config,
- keep SQLite-specific implementation inside backend modules where possible,
- keep desktop packaging isolated from framework code,
- review known hot spots after every upstream merge.

## Target Runtime Contract

SQLite-only local mode should be enabled per site with config like:

```json
{
  "db_type": "sqlite",
  "cache_backend": "local",
  "queue_backend": "sync",
  "realtime_backend": "noop",
  "pause_scheduler": 1
}
```

This is an opt-in local profile. It must not become the default path for normal Frappe installs.

## Sync Rules

1. Prefer adding SQLite behavior behind existing Frappe extension seams.
2. Keep conditionals small when shared files must be touched.
3. Do not move or rename core Frappe modules for desktop needs.
4. Keep desktop/Tauri/PyInstaller files under a top-level desktop area.
5. Do not commit generated build folders, local signing helpers, or app-bundle internals.
6. After an upstream sync, run the SQLite smoke suite before changing desktop code.

## High-Risk Core Files

These files are expected merge-conflict or behavior-review points.

| Area | Files | What To Watch |
| --- | --- | --- |
| DB factory | `frappe/database/__init__.py` | Preserve `db_type == "sqlite"` dispatch for setup, bootstrap, drop, connection, and CLI command lookup. |
| Site config | `frappe/config.py`, `frappe/installer.py` | Preserve config-driven SQLite selection. Do not require MariaDB host/user/password for SQLite sites. |
| SQLite backend | `frappe/database/sqlite/database.py`, `frappe/database/sqlite/schema.py`, `frappe/database/sqlite/setup_db.py`, `frappe/database/sqlite/framework_sqlite.db` | Recheck transactions, DDL rebuild logic, WAL pragmas, type map, placeholder translation, and bootstrap DB creation. |
| Base DB behavior | `frappe/database/database.py`, `frappe/database/schema.py`, `frappe/database/query.py`, `frappe/database/operator_map.py`, `frappe/query_builder/*` | Upstream query/compiler changes may assume MariaDB/Postgres semantics. Re-run filters, joins, reports, and migration tests. |
| Document locking | `frappe/model/document.py` | SQLite has no `FOR UPDATE`. Preserve the deliberate SQLite no-op or move it behind a DB capability method. |
| Cache | `frappe/__init__.py`, `frappe/utils/redis_wrapper.py`, `frappe/cache_manager.py`, `frappe/defaults.py`, `frappe/sessions.py`, `frappe/rate_limiter.py` | Preserve `cache_backend = local` and verify TTL, pattern delete, sessions, metadata invalidation, and rate limits. |
| Queue | `frappe/utils/background_jobs.py`, `frappe/utils/redis_queue.py` | Preserve `queue_backend = sync`. Verify `frappe.enqueue`, `enqueue_after_commit`, and clear errors for RQ-only APIs. |
| Scheduler | `frappe/utils/scheduler.py`, scheduled-job doctypes | Keep scheduler paused or explicitly sync-safe for SQLite Phase 1. |
| Realtime | `frappe/realtime.py`, `socketio.js`, `realtime/*`, `frappe/public/js/frappe/socketio_client.js` | Preserve `realtime_backend = noop`. Do not require Redis pubsub or socket.io for core local operations. |
| Search | `frappe/search/sqlite_search.py`, `frappe/search/full_text_search.py`, `frappe/utils/global_search.py` | Recheck SQLite FTS integration, global search rebuild, and background index build assumptions. |
| Backups | `frappe/utils/backups.py`, `frappe/database/__init__.py` | SQLite backup must copy/checkpoint the DB safely and not call MariaDB dump paths. |
| Tests | `frappe/tests/test_sqlite_only_runtime.py`, SQLite search tests | Expand tests before broadening support claims. Keep skips config-gated. |

## Desktop Boundary

Desktop is a packaging and UX layer. It should consume the SQLite profile; it should not define core framework behavior.

Expected desktop-owned concerns:

- first-run setup,
- site/data directory selection,
- sidecar process lifecycle,
- native menus,
- local backup command,
- app signing/notarization,
- asset/runtime bundling.

These should live under a top-level `desktop/` area long term. Current `desktop_shell/` and `desktop_runtime/` are acceptable for the PoC, but future cleanup should move them without touching Frappe core behavior.

## Upstream Sync Checklist

Run this after pulling/syncing new upstream Frappe changes.

```bash
git status --short
git diff --name-status upstream/version-16...HEAD -- frappe/database frappe/model frappe/utils frappe/realtime.py frappe/search frappe/installer.py frappe/config.py
```

Review changed hot spots against this watchlist, then run:

```bash
bench new-site sqlite-sync.localhost --db-type sqlite --admin-password admin --force
bench --site sqlite-sync.localhost migrate
bench --site sqlite-sync.localhost run-tests --module frappe.tests.test_sqlite_only_runtime
```

If desktop runtime is in scope for the sync:

```bash
npm run build
npm run tauri build
./scripts/sync-sidecar-into-app.sh
```

Then verify:

- `/login` returns HTTP 200,
- login CSS/JS assets return HTTP 200,
- a basic ToDo insert/update/delete works,
- no MariaDB or Redis process is required for the SQLite-only site,
- realtime no-op does not break document save or Desk boot,
- sync queue mode does not leave jobs silently pending.

## Agent Context Prompt

Use this prompt for an agent handling future upstream sync work:

```text
You are maintaining a Frappe fork with optional SQLite-only local runtime support.

Primary rule: preserve upstream Frappe structure and default MariaDB/PostgreSQL behavior. SQLite must remain opt-in through site config or environment config.

Read first:
- docs/sqlite-upstream-sync-watchlist.md
- docs/sqlite-full-coverage-tracker.md
- docs/SQLITE_ONLY_LIMITATIONS.md

Hot spots:
- frappe/database/__init__.py
- frappe/database/sqlite/*
- frappe/config.py
- frappe/installer.py
- frappe/model/document.py
- frappe/utils/redis_wrapper.py
- frappe/utils/background_jobs.py
- frappe/realtime.py
- frappe/search/*

Workflow:
1. Fetch upstream Frappe.
2. Merge or rebase in small steps.
3. Resolve conflicts by preserving upstream defaults and SQLite opt-in behavior.
4. Keep desktop packaging isolated from Frappe core.
5. Run SQLite site create, migrate, and sqlite-only runtime tests.
6. Update the coverage tracker with any changed status or new gaps.

Do not:
- restructure the Frappe repo,
- make SQLite the default DB,
- require desktop packaging for SQLite runtime tests,
- commit generated desktop bundles, PyInstaller internals, node_modules, or local signing scripts.
```
