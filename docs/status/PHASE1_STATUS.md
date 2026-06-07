# Phase 1 Status

Date: 2026-06-07
Phase: 1
Overall: DONE

## P0 Checklist

| Item | Status | Note |
|---|---|---|
| P0-1 | DONE | 15 automated tests pass with MariaDB/Redis stopped |
| P0-1b | DONE | No-infra gate validated |
| P0-2 | DONE | HTTP/API validated (login, /desk 200, ToDo CRUD) |
| P0-2b | DONE | Manual browser: login, Todo, global search — MariaDB+Redis stopped |
| P0-3 | DONE | LocalCache TTL via setex/expire implemented and tested |
| P0-4 | DONE | after_commit/after_rollback tested |
| P0-5 | DONE | get_list filters tested |
| P0-6 | DONE | metadata/defaults/cache invalidation tested |
| P0-7 | DONE | scheduler early-return added; rq_job sync guard added; 3 new tests pass |
| P0-8 | DONE | migrate idempotency verified (two consecutive migrates) |
| P0-9 | DONE | TestSQLiteBackupRestore 3 tests pass; sqlite-backup-restore.md added |
| P0-10 | DONE | SQLITE_ONLY_LIMITATIONS.md exists |

## Test Suite

Ran 15 tests — OK (all pass with MariaDB and Redis stopped)

```
frappe.tests.test_sqlite_only_runtime.TestSQLiteBackupRestore
  ✔ test_sqlite_db_file_exists
  ✔ test_sqlite_db_integrity
  ✔ test_sqlite_offline_backup

frappe.tests.test_sqlite_only_runtime.TestSQLiteOnlyRuntime
  ✔ test_after_commit_reset_on_rollback
  ✔ test_local_cache
  ✔ test_local_cache_ttl
  ✔ test_metadata_and_defaults_cache
  ✔ test_noop_realtime
  ✔ test_publish_realtime_noop
  ✔ test_runtime_backends
  ✔ test_scheduler_paused_gate
  ✔ test_sync_enqueue
  ✔ test_sync_enqueue_after_commit
  ✔ test_sync_enqueue_feature_gate
  ✔ test_todo_crud_and_filters
```

## Server Access

- URL: http://localhost:8105
- Credentials: Administrator / admin
- Site: sqliteonly.localhost
- Bench: /workspace/development/sqlitepoc (container) / /Users/safwan/Code/docker/fdocker/development/sqlitepoc (host)
- Port mapping: container 8005 → host 8105

## Phase 1 Exit Criteria — All Met

1. ✅ Fresh SQLite site created and migrated
2. ✅ Redis and MariaDB can be stopped — all tests still pass
3. ✅ Automated CLI smoke passes (15 tests)
4. ✅ Browser Desk smoke passes (manual: login, Todo, global search)
5. ✅ ToDo CRUD works from UI and Python
6. ✅ Migrate is idempotent
7. ✅ Cache TTL/session tests pass
8. ✅ Disabled realtime/RQ/scheduler paths fail gracefully
9. ✅ Limitations documented (SQLITE_ONLY_LIMITATIONS.md)

## Key Files Changed (frappe source)

- `frappe/database/sqlite/database.py` — SQLite connection, CONCAT_WS shim
- `frappe/utils/redis_wrapper.py` — LocalCache with real TTL
- `frappe/utils/background_jobs.py` — sync queue mode
- `frappe/realtime.py` — noop backend
- `frappe/utils/scheduler.py` — early return when pause_scheduler=1
- `frappe/core/doctype/rq_job/rq_job.py` — empty-return guard for queue_backend=sync
- `frappe/tests/test_sqlite_only_runtime.py` — 15 tests across 2 classes

## Docs Added

- `docs/sqlite-site-access.md` — URL, credentials, how to start/stop
- `docs/sqlite-backup-restore.md` — safe offline copy, WAL notes, restore procedure
- `docs/SQLITE_ONLY_LIMITATIONS.md` — disabled features and supported scope
- `docs/status/PHASE1_STATUS.md` — this file

## Next (Phase 2)

See `sqlite-production-readiness.md` Milestone B: query/filter/join matrix, schema mutation coverage, search, scheduler/sync queue depth.
