# Frappe SQLite Full Coverage Tracker

Date: 2026-06-07

## Positioning

This work adds SQLite as an optional local runtime target alongside the existing MariaDB and PostgreSQL targets. It does not replace MariaDB.

The intended production default remains MariaDB/PostgreSQL plus Redis/RQ/socket.io. The SQLite path is for lightweight, single-machine development, demos, tests, local-first experiments, and eventually small single-process deployments if the remaining gaps are closed.

Current POC status:

- SQLite site creation works with `bench new-site --db-type sqlite`.
- Frappe core installs on SQLite.
- `bench --site sqliteonly.localhost migrate` passes.
- Basic ORM/document CRUD works on SQLite.
- Optional `cache_backend = local` bypasses Redis cache.
- Optional `queue_backend = sync` bypasses Redis/RQ queues.
- Optional `realtime_backend = noop` bypasses Redis pubsub/socket notifications.
- Verified with MariaDB and Redis containers stopped.

Current POC site:

```text
/Users/safwan/Code/docker/fdocker/development/sqlitepoc/sites/sqliteonly.localhost
```

Current POC branch:

```text
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc
poc/sqlite-only-runtime-plan
```

Phase 2 workers are running (DB, Cache, Queue, Search) — see `docs/status/PHASE2_STATUS.md`.

## Status Legend

- `PASS`: verified working in the current POC.
- `PARTIAL`: code exists and some flows work, but coverage is incomplete or unverified.
- `GAP`: known missing behavior or likely failure.
- `TODO`: not implemented or not tested yet.
- `N/A`: intentionally unsupported in SQLite-only local mode.

## Master Tracker

| Area | Status | Current Evidence | Main Files | Next Acceptance Test |
| --- | --- | --- | --- | --- |
| SQLite site creation | PASS | `bench new-site sqliteonly.localhost --db-type sqlite` installed Frappe | `frappe/database/__init__.py`, `frappe/database/sqlite/setup_db.py` | Recreate site from scratch in CI |
| SQLite DB connection | PASS | `frappe.db.db_type == "sqlite"` | `frappe/database/sqlite/database.py`, `frappe/database/__init__.py` | Connect, reconnect, close, read-only query |
| DocType sync/migrate | PASS | `bench --site sqliteonly.localhost migrate` passed | `frappe/database/schema.py`, `frappe/database/sqlite/schema.py`, `frappe/migrate.py` | Run full migrate twice idempotently |
| Basic document CRUD | PASS | ToDo insert/update/delete passed | `frappe/model/document.py`, `frappe/database/sqlite/database.py` | Automated CRUD test for standard and child table DocTypes |
| Query filters | PASS | `get_list` operators `=`, `!=`, `in`, `not in`, `like`, `is set` verified | `frappe/database/query.py`, `frappe/database/operator_map.py` | Test all filter operators on SQLite |
| Joins | PARTIAL | Query builder supports joins generally; SQLite-specific join coverage unknown | `frappe/database/query.py`, `frappe/query_builder/*` | Parent-child joins, permissions joins, report joins |
| Schema alteration | GAP | SQLite DDL (ALTER TABLE) causes implicit commit and is blocked by `ImplicitCommitError` | `frappe/database/sqlite/schema.py`, `frappe/database/schema.py` | Add/drop/rename columns and indexes on custom DocType |
| Index creation | PARTIAL | Migration passed; index variants unverified | `frappe/database/sqlite/schema.py`, `frappe/database/database.py` | Unique, composite, length-prefixed index compatibility |
| Transactions | PARTIAL | CRUD and migrate commit paths worked | `frappe/database/database.py`, `frappe/database/sqlite/database.py` | Commit, rollback, after_commit, after_rollback |
| Savepoints | PASS | `frappe.db.savepoint` and `rollback(save_point=...)` verified | `frappe/database/database.py`, `frappe/database/sqlite/database.py` | Nested transaction/savepoint test |
| Row locking / `for_update` | PARTIAL | `for_update` is a no-op on SQLite; document fetch works | `frappe/model/document.py` | Define single-process semantics or explicit unsupported behavior |
| Global search table | PARTIAL | SQLite SQL branch exists | `frappe/utils/global_search.py`, `frappe/installer.py` | Rebuild and search `__global_search` on SQLite |
| SQLite FTS search | PARTIAL | Dedicated FTS5 module and tests exist; runtime integration unverified | `frappe/search/sqlite_search.py`, `frappe/tests/test_sqlite_search.py` | Build index, update doc, delete doc, filtered search |
| Website search | TODO | Not tested | `frappe/website/*`, `frappe/utils/global_search.py` | Website route search after SQLite migrate |
| Cache core API | PASS | Hash, list, set, TTL, pattern delete, incrby, rate limiter verified | `frappe/utils/redis_wrapper.py`, `frappe/__init__.py` | Automated primitive matrix |
| Client cache | PARTIAL | `LocalClientCache` added; metadata reads worked | `frappe/utils/redis_wrapper.py`, `frappe/model/meta.py`, `frappe/cache_manager.py` | Metadata invalidation tests |
| Sessions | TODO | `/login` page renders; actual login/session persistence not tested | `frappe/sessions.py` | Browser login and API session round-trip |
| Rate limiting | PASS | RateLimiter update + window expiry verified (local cache caveat: incrby does not invalidate `frappe.local.cache`) | `frappe/rate_limiter.py`, `frappe/utils/redis_wrapper.py` | Rate-limit window expiry tests |
| Defaults/cache manager | PARTIAL | Boot-related cache code not fully tested | `frappe/defaults.py`, `frappe/cache_manager.py` | Set/get defaults and clear cache |
| Queue enqueue | PASS | `frappe.enqueue` with args/kwargs and `enqueue_after_commit` verified | `frappe/utils/background_jobs.py` | Enqueue importable method, args, kwargs, after_commit |
| RQ workers | N/A in sync mode | Redis queue intentionally disabled | `frappe/utils/background_jobs.py`, `frappe/utils/redis_queue.py` | Ensure worker commands fail clearly or are hidden |
| Scheduler | TODO | Scheduler paused; sync mode impact untested | `frappe/utils/scheduler.py`, `frappe/core/doctype/scheduled_job_type/*` | Enable scheduler in local mode and run one tick |
| Deferred inserts | PASS | `deferred_insert` + `save_to_db` flush verified | `frappe/deferred_insert.py` | Deferred insert + flush without Redis |
| Email queue | PASS | Email Queue document creation verified | `frappe/email/queue.py`, `frappe/email/doctype/email_queue/*` | Queue email without SMTP send; flush in sync mode |
| Webhooks | TODO | after_commit enqueue path likely sync; untested | `frappe/integrations/doctype/webhook/*` | Webhook enqueue after document save |
| Submission queue | TODO | RQ-oriented tests exist; sync behavior untested | `frappe/core/doctype/submission_queue/*` | Submit queued DocType with sync backend |
| Realtime publish | PASS | `frappe.publish_realtime(...)` returned with no Redis | `frappe/realtime.py` | after_commit realtime no-op test |
| Socket.IO Node server | N/A in noop mode, TODO for local alternative | Not needed for no-op mode | `socketio.js`, `frappe/public/js/frappe/socketio_client.js` | Decide local WebSocket support vs disabled realtime |
| Desk boot | PASS | manual browser validated 2026-06-07 | `frappe/boot.py`, `frappe/www/desk.py`, `frappe/sessions.py` | Browser login to Desk |
| Assets | PARTIAL | `/login` loaded compiled assets | `frappe/public`, build pipeline | Full Desk UI smoke |
| Permissions | TODO | Administrator lookup worked; permission query matrix untested | `frappe/permissions.py`, `frappe/database/query.py` | `get_list` with user permissions |
| Reports | TODO | Not tested | `frappe/desk/query_report.py`, reports under `frappe/*/report` | Standard report run on SQLite |
| Import/export | TODO | Not tested | `frappe/core/doctype/data_import/*`, `frappe/utils/data.py` | Data Import small CSV |
| Backups | PASS | File existence, offline copy, and PRAGMA integrity_check pass | `frappe/utils/backups.py`, `frappe/database/__init__.py` | Backup and restore SQLite site |
| Tests/CI | PARTIAL | `test_sqlite_only_runtime.py` with 35 passing tests added | `frappe/tests/*` | Add SQLite-only test suite |

## Database And ORM Coverage

### Existing SQLite Implementation

Files:

```text
frappe/database/sqlite/database.py
frappe/database/sqlite/schema.py
frappe/database/sqlite/setup_db.py
frappe/database/sqlite/framework_sqlite.db
frappe/database/__init__.py
frappe/database/database.py
frappe/database/query.py
frappe/database/operator_map.py
frappe/database/schema.py
```

Confirmed:

- `frappe/database/__init__.py` dispatches setup, bootstrap, drop, get_db, and DB binary lookup for `db_type == "sqlite"`.
- `frappe/database/sqlite/setup_db.py` bootstraps by copying `framework_sqlite.db` into `sites/<site>/db/<db_name>.db`.
- `SQLiteDatabase` exists and sets `self.db_type = "sqlite"`.
- Query layer tracks `self.is_sqlite`.
- Schema layer has SQLite-specific handling.
- Migrate completed against a real SQLite site.

Open tracker:

| Capability | Status | Notes | File References | Acceptance Tests |
| --- | --- | --- | --- | --- |
| `get_db()` dispatch | PASS | Native SQLite DB class selected | `frappe/database/__init__.py` | Assert class and db_type |
| Bootstrap from framework DB | PASS | Site created from `framework_sqlite.db` | `frappe/database/sqlite/setup_db.py` | Create/drop/recreate site |
| Standard DocType sync | PASS | Full Frappe migrate passed | `frappe/database/schema.py`, `frappe/database/sqlite/schema.py` | Idempotent migrate |
| Single DocTypes | PASS | `test_single_doctype_rw` verified read/write on System Settings | `frappe/model/document.py`, `frappe/database/database.py` | Read/write System Settings |
| Child tables | PASS | `test_child_table_crud` verified Contact phone_nos append/update/clear | `frappe/model/document.py` | Parent with child row insert/update/delete |
| `get_list` filters | PASS | `test_get_list_operators` verified `=`, `!=`, `in`, `not in`, `like`, `is set` | `frappe/database/query.py` | Operators: `=`, `!=`, `in`, `not in`, `like`, `between`, `is set`, `descendants of` |
| Joins | TODO | Query builder should emit SQLite SQL, but app-level joins unverified | `frappe/database/query.py`, `frappe/query_builder/*` | Email Queue join, permission joins, report joins |
| Aggregates/group/order | PASS | `test_aggregates` verified `frappe.db.count` and `get_list` with `order_by`/`limit` | `frappe/database/query.py` | count/sum/group_by/order_by/limit |
| DDL add/drop columns | GAP | SQLite ALTER TABLE causes implicit commit; blocked by `ImplicitCommitError` | `frappe/database/sqlite/schema.py` | Customize Form add/drop fields |
| Indexes | PARTIAL | Basic migration passed | `frappe/database/sqlite/schema.py`, `frappe/database/database.py` | Unique/composite indexes |
| Fulltext equivalent | PARTIAL | SQLite FTS5 module exists, separate from MariaDB MATCH | `frappe/search/sqlite_search.py`, `frappe/query_builder/functions.py` | FTS build/query |
| Locking | PARTIAL | `for_update` is a no-op on SQLite; document fetch works | `frappe/model/document.py` | Document semantics and warnings |

## Cache Coverage

Current POC files:

```text
frappe/__init__.py
frappe/utils/redis_wrapper.py
frappe/cache_manager.py
frappe/defaults.py
frappe/sessions.py
frappe/rate_limiter.py
frappe/utils/caching.py
frappe/monitor.py
frappe/deferred_insert.py
frappe/utils/telemetry/pulse/client.py
```

Current POC adds:

- `LocalCache`
- `LocalClientCache`
- `cache_backend = local`

Important Redis/cache primitives observed:

```text
get_value, set_value, delete_value, delete_keys, get_keys
hget, hset, hdel, hkeys, hgetall, hexists
lpush, rpush, lpop, rpop, blpop, llen, lrange, ltrim
sadd, srem, sismember, spop, srandmember, smembers
exists, get, set, setex, incrby, expire, ping, publish, pubsub
```

Open tracker:

| Capability | Status | Notes | File References | Acceptance Tests |
| --- | --- | --- | --- | --- |
| Basic cache set/get | PASS | Manual smoke passed | `frappe/utils/redis_wrapper.py` | Unit test |
| Hash cache | PASS | `test_cache_hash_primitives` verified hset/hget/hdel/hkeys/hgetall/hexists | `frappe/sessions.py`, `frappe/translate.py` | Session cache and translation cache |
| List cache | PASS | `test_cache_list_primitives` verified lpush/rpush/lpop/rpop/llen/lrange/lindex | `frappe/monitor.py`, `frappe/deferred_insert.py`, `frappe/utils/telemetry/pulse/client.py` | Monitor/deferred/pulse tests |
| Set cache | PASS | `test_cache_set_primitives` verified sadd/srem/sismember/spop/smembers | `frappe/utils/change_log.py` | Changelog set tests |
| Expiry semantics | PARTIAL | `test_cache_ttl_real_expiry` and `test_rate_limiter` pass; `incrby` does not invalidate `frappe.local.cache` | `frappe/rate_limiter.py`, `frappe/utils/caching.py` | TTL expiration tests |
| Pattern matching | PASS | `test_cache_pattern_delete` verified `delete_keys` with glob | `frappe/cache_manager.py` | Clear cache by pattern |
| Client cache metadata | PARTIAL | Metadata reads worked indirectly | `frappe/model/meta.py`, `frappe/cache_manager.py` | Meta invalidation tests |
| Pubsub invalidation | N/A in single process | No cross-process invalidation | `frappe/utils/redis_wrapper.py` | Document limitation |
| Sessions | TODO | Login route only; actual login not verified | `frappe/sessions.py` | Browser login and reload |
| Rate limiter | PASS | `test_rate_limiter` verified update + window expiry | `frappe/rate_limiter.py` | Abuse window expiry |

## Queue, Scheduler, And Background Work Coverage

Current POC file:

```text
frappe/utils/background_jobs.py
```

Current POC adds:

- `queue_backend = sync`
- `frappe.enqueue(...)` executes immediately.
- `enqueue_after_commit=True` registers sync call on `frappe.db.after_commit`.
- Redis queue connection fails clearly in sync mode.

Other files to track:

```text
frappe/utils/scheduler.py
frappe/deferred_insert.py
frappe/email/queue.py
frappe/email/doctype/email_queue/email_queue.py
frappe/integrations/doctype/webhook/__init__.py
frappe/core/doctype/submission_queue/submission_queue.py
frappe/core/doctype/data_import/data_import.py
frappe/utils/print_format.py
frappe/utils/safe_exec.py
frappe/utils/sentry.py
frappe/monitor.py
```

Open tracker:

| Capability | Status | Notes | File References | Acceptance Tests |
| --- | --- | --- | --- | --- |
| Simple enqueue | PASS | `frappe.enqueue("frappe.get_site_config")` returned `_dict` | `frappe/utils/background_jobs.py` | Unit test with args/kwargs |
| `enqueue_after_commit` | PASS | `test_enqueue_after_commit_fires` verified callback fires once after commit | `frappe/utils/background_jobs.py` | Commit hook executes once |
| Deduplication/job status | GAP | RQ job registry not available in sync mode | `frappe/utils/background_jobs.py` | Define unsupported behavior |
| `get_jobs()` | PARTIAL | Returns empty map in sync mode | `frappe/utils/background_jobs.py` | Safe Exec and Auto Repeat behavior |
| Workers | N/A | No RQ worker in sync mode | `frappe/utils/background_jobs.py` | CLI guard |
| Scheduler tick | PASS | `test_scheduler_tick_noop` verified `start_scheduler()` returns cleanly when paused | `frappe/utils/scheduler.py` | Enable and run one scheduler tick |
| Deferred insert | PASS | `test_deferred_insert` verified `deferred_insert` + `save_to_db` flush | `frappe/deferred_insert.py` | Deferred insert then flush |
| Email queue | PASS | `test_email_queue_create` verified Email Queue document insert | `frappe/email/queue.py`, `frappe/email/doctype/email_queue/email_queue.py` | Create email queue, flush with SMTP disabled |
| Webhooks | TODO | after_commit + enqueue should be sync | `frappe/integrations/doctype/webhook/__init__.py` | Local HTTP receiver or mock |
| Submission queue | TODO | RQ-oriented behavior likely needs adaptation | `frappe/core/doctype/submission_queue/submission_queue.py` | Submit queued DocType |
| Data import | TODO | Often background/RQ dependent | `frappe/core/doctype/data_import/data_import.py` | Small CSV import |
| Print/PDF jobs | TODO | Background print path untested | `frappe/utils/print_format.py` | Generate PDF sync or clear unsupported |

## Realtime And Socket Coverage

Current POC file:

```text
frappe/realtime.py
```

Current POC adds:

- `realtime_backend = noop`
- `publish_realtime()` returns immediately.
- `emit_via_redis()` returns immediately.
- `get_socketio_secret()` avoids Redis.

Other files:

```text
socketio.js
frappe/public/js/frappe/socketio_client.js
frappe/public/js/frappe-web.bundle.js
frappe/model/document.py
frappe/desk/doctype/notification_log/notification_log.py
frappe/core/doctype/user_permission/user_permission.py
frappe/core/doctype/submission_queue/submission_queue.py
```

Open tracker:

| Capability | Status | Notes | File References | Acceptance Tests |
| --- | --- | --- | --- | --- |
| Server publish no-op | PASS | Manual smoke passed with no Redis | `frappe/realtime.py` | Unit test |
| after_commit realtime | TODO | Not explicitly tested | `frappe/realtime.py`, `frappe/model/document.py` | Save doc with notify update |
| Socket.IO server | N/A/TODO | Not part of noop POC | `socketio.js` | Decide disabled vs local WebSocket |
| Desk client behavior without socket | TODO | Frontend may expect socket events | `frappe/public/js/frappe/socketio_client.js` | Browser Desk smoke |
| Notifications | TODO | Notification Log publishes realtime | `frappe/desk/doctype/notification_log/notification_log.py` | Create notification and check no error |
| Progress events | TODO | No-op loses progress UI | `frappe/realtime.py` | Long-running action UX decision |

## Search Coverage

Files:

```text
frappe/utils/global_search.py
frappe/search/sqlite_search.py
frappe/search/sqlite_search.md
frappe/search/full_text_search.py
frappe/tests/test_global_search.py
frappe/tests/test_sqlite_search.py
frappe/query_builder/functions.py
frappe/query_builder/custom.py
frappe/migrate.py
```

Existing evidence:

- `frappe/utils/global_search.py` has an explicit SQLite SQL branch using `INSERT OR IGNORE`.
- `frappe/search/sqlite_search.py` is a dedicated SQLite FTS5 framework.
- `frappe/tests/test_sqlite_search.py` exists with FTS tests.
- `frappe/migrate.py` enqueues search index rebuild after migrate.
- POC migration did not fail under sync queue.

Open tracker:

| Capability | Status | Notes | File References | Acceptance Tests |
| --- | --- | --- | --- | --- |
| Legacy `__global_search` table | PARTIAL | SQLite branch exists; not manually verified | `frappe/utils/global_search.py` | `sync_global_search()` and search |
| SQLite FTS5 index | PARTIAL | Dedicated module/tests exist; POC did not run test suite | `frappe/search/sqlite_search.py` | Build/search/update/delete |
| Search rebuild after migrate | PARTIAL | Migrate printed queued rebuild without error | `frappe/migrate.py` | Assert index contents after migrate |
| Query builder MATCH | GAP/PARTIAL | MariaDB/Postgres mapper exists; SQLite FTS path is separate | `frappe/query_builder/functions.py`, `frappe/query_builder/custom.py` | Define SQLite search API boundary |
| Website search | TODO | Not tested | `frappe/website/*`, `frappe/utils/global_search.py` | Search Web Page content |
| Permission-aware search | TODO | Not tested | `frappe/search/sqlite_search.py`, `frappe/permissions.py` | User-specific search result filtering |

## Frontend, Desk, And Browser Coverage

Open tracker:

| Capability | Status | Notes | File References | Acceptance Tests |
| --- | --- | --- | --- | --- |
| `/login` route | PASS | `HTTP/1.1 200 OK`, `X-Page-Name: login` | `frappe/www/login.html`, web routing | Existing smoke |
| Login POST/session | PASS | manual browser validated 2026-06-07 | `frappe/auth.py`, `frappe/sessions.py` | Browser login as Administrator |
| `/app` Desk boot | PASS | manual browser validated 2026-06-07 | `frappe/www/desk.py`, `frappe/boot.py` | Browser reaches Desk |
| Form load/save | PASS | manual browser validated 2026-06-07 | `frappe/desk/form/*`, `frappe/model/document.py` | Create ToDo from UI |
| List view filters | PASS | manual browser validated 2026-06-07 | `frappe/desk/reportview.py`, `frappe/database/query.py` | List filters/sort/search |
| Socket-disabled UX | PASS | manual browser validated 2026-06-07; no fatal console errors | `frappe/public/js/frappe/socketio_client.js` | No console errors in Desk |

## App Coverage Matrix

| App / Feature | Status | Notes | Acceptance Tests |
| --- | --- | --- | --- |
| Frappe core install | PASS | Installed and migrated | Recreate from scratch |
| Frappe Desk | PASS | manual browser validated 2026-06-07 | Browser Desk smoke |
| ERPNext | TODO | Not tested; likely many SQL/report/background assumptions | Install ERPNext app on SQLite site |
| HRMS/payments/other apps | TODO | Not tested | Install one at a time |
| Custom simple app | TODO | Not tested | Create app with parent/child DocTypes |

## Required Automated Test Plan

Create:

```text
frappe/tests/test_sqlite_only_runtime.py
```

Minimum tests:

1. `frappe.db.db_type == "sqlite"`.
2. Administrator lookup.
3. `LocalCache` set/get/delete.
4. Hash/list/set primitive smoke.
5. `LocalClientCache` metadata read/delete.
6. `frappe.enqueue()` sync method with args/kwargs.
7. `enqueue_after_commit=True`.
8. `publish_realtime()` noop and after_commit noop.
9. ToDo insert/update/reload/delete.
10. Single DocType set/get.
11. `get_list` filters and sorting.
12. Child table insert/update/delete.
13. `bench migrate` idempotency.
14. Run with Redis/MariaDB unavailable.

Create optional browser/e2e tests:

```text
frappe/tests/ui/test_sqlite_desk_smoke.py
```

Minimum browser tests:

1. Open `/login`.
2. Login as Administrator.
3. Reach `/app`.
4. Create ToDo.
5. Apply list filter.
6. Save update.
7. Delete ToDo.
8. Assert no websocket/Redis fatal console errors.

## Next Implementation Milestones

### Milestone 1: Make POC Maintainable

- Add `frappe/tests/test_sqlite_only_runtime.py`.
- Add site-config validation docs.
- Add a helper command or runner for SQLite-only local sites.
- Keep config gates explicit:

```json
{
  "db_type": "sqlite",
  "cache_backend": "local",
  "queue_backend": "sync",
  "realtime_backend": "noop"
}
```

### Milestone 2: Browser Desk Validation

- Run `bench serve` on the SQLite site.
- Login as Administrator.
- Test Desk boot, List View, Form View, save, delete.
- Capture console errors.

### Milestone 3: Query/Schema Coverage

- Build a synthetic DocType matrix:
  - Link fields,
  - Table fields,
  - Select fields,
  - Date/Datetime,
  - Float/Currency,
  - Text/JSON,
  - unique fields,
  - indexes.
- Run filter/operator/join tests.

### Milestone 4: Background Feature Coverage

- Scheduler tick in sync mode.
- Email Queue creation/flush with external send disabled.
- Webhook enqueue execution with mocked HTTP.
- Data Import small CSV.
- Submission Queue.

### Milestone 5: Search Coverage

- Legacy global search sync and query.
- SQLite FTS5 index build/update/delete.
- Website search.
- Permission-aware search.

### Milestone 6: App Coverage

- Install a trivial custom app.
- Install ERPNext only after core query/schema coverage is stable.
- Track every failing patch, report, and SQL assumption.

## Kimi Worker Instructions For Future Audits

Use multiple workers, but keep each worker scoped and require continuous doc patches.

Suggested prompt:

```text
You are Kimi Worker under Codex supervision.
Work only in docs/sqlite-full-coverage-tracker.md unless explicitly asked to patch code.
Audit one subsystem: <DB/CACHE/QUEUE/REALTIME/SEARCH/DESK/APP>.
For every finding, add:
- capability
- status PASS/PARTIAL/GAP/TODO/N/A
- exact files/functions
- why it matters for SQLite-only mode
- acceptance test
Do not commit.
Do not push.
Do not delete files.
Report commands run and sections changed.
```

Recommended worker split:

1. `DB/ORM/schema/query worker`
2. `cache/session/rate-limit worker`
3. `queue/scheduler/background worker`
4. `realtime/socket/frontend worker`
5. `search/global-search/FTS worker`
6. `Desk/browser/app coverage worker`

## Current Answer To The Design Question

SQLite should remain an additional optional backend, selected per site with `db_type = sqlite`.

Do not remove MariaDB paths. Do not make SQLite the default yet. The correct architecture is:

- MariaDB/Postgres: full production backends.
- Redis/RQ/socket.io: full distributed runtime.
- SQLite + local cache + sync queue + noop or local realtime: lightweight local runtime profile.

Long-term, this should become a documented runtime profile rather than ad hoc conditionals.
