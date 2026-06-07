# SQLite-Only Runtime Limitations

Date: 2026-06-07

## Scope

SQLite-only runtime is an optional local profile. It does not replace MariaDB or PostgreSQL.

Phase 1 target config:

```json
{
  "db_type": "sqlite",
  "cache_backend": "local",
  "queue_backend": "sync",
  "realtime_backend": "noop",
  "pause_scheduler": 1,
  "disable_async": 1
}
```

Phase 1 supports core framework operations:

- site creation,
- migration,
- database/document API,
- basic Desk/login validation,
- local metadata/cache/defaults,
- synchronous background calls needed for correctness.

## Intentionally Disabled Or Degraded

| Feature | Phase 1 Behavior | Impact |
| --- | --- | --- |
| Realtime/socket.io | Disabled with `realtime_backend = noop` | No live notifications, progress events, list refresh, or socket updates |
| Redis cache | Replaced with in-process `LocalCache` | No cross-process invalidation; only suitable for single-process local runtime |
| RQ workers | Disabled with `queue_backend = sync` | Jobs run inline; no worker isolation, retries, queue depth, or RQ job history |
| Scheduler daemon | Paused by default | Scheduled jobs do not run unless explicitly invoked later |
| RQ Job dashboard | Unsupported in sync mode | No Redis/RQ registry exists |
| Search rebuild after migrate | Must be explicit or sync-safe | Search coverage is not Phase 1 core |
| Telemetry/monitor Redis lists | Local-only or disabled | Diagnostics may be incomplete |

## Must Not Be Disabled

These are required for Phase 1:

- SQLite DB connection and migration.
- DocType sync.
- Document CRUD.
- metadata and defaults.
- sessions/login/CSRF.
- permissions.
- commit/rollback hooks.
- synchronous `frappe.enqueue`.

## Known Technical Limits

- SQLite concurrency differs from MariaDB. Phase 1 assumes a local single-process profile.
- `for_update` row locking is not equivalent on SQLite.
- Local cache TTL support still needs hardening for session/rate-limit correctness.
- Query-builder compatibility is incomplete; `CONCAT_WS` is now registered for SQLite, but other SQL functions may surface as tests expand.
- Full Desk/browser coverage is pending.
- ERPNext and other apps are not covered.

## Current Validated Tests

Manual validation:

- SQLite site created and migrated.
- Redis and MariaDB stopped.
- SQLite site console smoke passed.
- `/login` returned `HTTP/1.1 200 OK`.

Automated validation:

```bash
bench --site sqliteonly.localhost run-tests --module frappe.tests.test_sqlite_only_runtime
```

Result:

```text
Ran 7 tests
OK
```

Covered:

- runtime backend config,
- Administrator lookup,
- local cache primitives,
- sync enqueue,
- `enqueue_after_commit`,
- rollback clearing after-commit callbacks,
- noop realtime,
- ToDo CRUD and list filter.
