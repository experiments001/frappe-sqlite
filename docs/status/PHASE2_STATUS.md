# Phase 2 Status

Date: 2026-06-07
Phase: 2 (Milestone B — Frappe Core Beta)
Overall: IN_PROGRESS (worker results merged)

## Workers

| Worker | Handle | Scope |
| --- | --- | --- |
| DB | kimi/p2-db | Database/ORM, query, schema, locking, permissions, reports |
| CACHE | kimi/p2-cache | LocalCache, sessions, rate limiting, defaults, metadata |
| QUEUE | kimi/p2-queue | Scheduler, background jobs, email, webhooks, data import, realtime |
| SEARCH | kimi/p2-search | Global search, FTS5, website search, permission-aware search |

## Merged Test Results

```
bench --site sqliteonly.localhost run-tests --module frappe.tests.test_sqlite_only_runtime
```

**Ran 36 tests — OK (35 passed, 0 skipsped)**

| Test Class | Tests | Pass | Skip | Fail |
| --- | --- | --- | --- | --- |
| TestSQLiteOnlyRuntime | 12 | 12 | 0 | 0 |
| TestSQLiteBackupRestore | 3 | 3 | 0 | 0 |
| TestSQLiteDBCoverage | 7 | 6 | 1 | 0 |
| TestSQLiteCacheCoverage | 8 | 8 | 0 | 0 |
| TestSQLiteQueueCoverage | 6 | 6 | 0 | 0 |
| **Total** | **36** | **35** | **1** | **0** |

### Passing Tests by Class

**TestSQLiteOnlyRuntime**
- test_runtime_backends
- test_local_cache
- test_local_cache_ttl
- test_metadata_and_defaults_cache
- test_sync_enqueue
- test_sync_enqueue_after_commit
- test_after_commit_reset_on_rollback
- test_noop_realtime
- test_publish_realtime_noop
- test_sync_enqueue_feature_gate
- test_scheduler_paused_gate
- test_todo_crud_and_filters

**TestSQLiteBackupRestore**
- test_sqlite_db_file_exists
- test_sqlite_offline_backup
- test_sqlite_db_integrity

**TestSQLiteDBCoverage**
- test_single_doctype_rw
- test_child_table_crud
- test_get_list_operators
- test_aggregates
- test_savepoints
- test_for_update_noop

**TestSQLiteCacheCoverage**
- test_cache_hash_primitives
- test_cache_list_primitives
- test_cache_set_primitives
- test_cache_ttl_real_expiry
- test_cache_incrby
- test_cache_pattern_delete
- test_rate_limiter
- test_session_cache

**TestSQLiteQueueCoverage**
- test_enqueue_with_args
- test_enqueue_after_commit_fires
- test_deferred_insert
- test_email_queue_create
- test_scheduler_tick_noop
- test_background_job_no_redis

### Skipped Tests

| Test | Reason |
| --- | --- |
| TestSQLiteDBCoverage.test_schema_add_drop_field | GAP: SQLite DDL (ALTER TABLE) causes implicit commit and is blocked by `ImplicitCommitError` |

## Remaining GAPs

1. **SQLite DDL / Schema Alteration** — `ALTER TABLE` triggers implicit commit; Frappe's SQLite adapter raises `ImplicitCommitError`. Custom field add/drop via Customize Form will fail. Needs either `PRAGMA foreign_keys` + table-rebuild approach or explicit single-process DDL semantics.
2. **LocalCache `incrby` does not invalidate `frappe.local.cache`** — `get_value` caches `None` on first miss; `incrby` updates `_values` but not `frappe.local.cache`. Tests work around this by popping the key from local cache before reading. Production rate limiting works across requests but may behave unexpectedly within the same request if read twice.
3. **Search coverage unchanged** — Search worker did not add new test class (`TestSQLiteSearchCoverage` was missing). Legacy global search SQLite branch and FTS5 module remain unverified in the runtime test suite.
4. **Sessions** — No automated browser login/API session round-trip test added.
5. **Permissions, Reports, Import/Export, Webhooks, Submission Queue, Data Import, Print/PDF** — Still TODO; no worker tests added.
6. **ERPNext / App compatibility** — Not tested.

## Code Fixes Merged to Main

| File | Source Worktree | Change |
| --- | --- | --- |
| `frappe/deferred_insert.py` | kimi-p2-queue | Handle bytes-to-string decode before `json.loads` |
| `frappe/utils/redis_wrapper.py` | kimi-p2-cache | Add `delete()` method to `LocalCache`; add `lindex()` method |
| `frappe/utils/global_search.py` | kimi-p2-search | Add SQLite SQL branch for `sync_global_search()` and search query |

## Master Tracker Items

| # | Capability | Status | Worker | Acceptance Test |
| --- | --- | --- | --- | --- |
| 1 | Query filters | PASS | DB | Test all filter operators on SQLite |
| 2 | Joins | PARTIAL | DB | Parent-child joins, permissions joins, report joins |
| 3 | Schema alteration | GAP | DB | Add/drop/rename columns and indexes on custom DocType |
| 4 | Index creation | PARTIAL | DB | Unique, composite, length-prefixed index compatibility |
| 5 | Transactions | PARTIAL | DB | Commit, rollback, after_commit, after_rollback |
| 6 | Savepoints | PASS | DB | Nested transaction/savepoint test |
| 7 | Row locking / `for_update` | PARTIAL | DB | Define single-process semantics or explicit unsupported behavior |
| 8 | Global search table | PARTIAL | SEARCH | Rebuild and search `__global_search` on SQLite |
| 9 | SQLite FTS search | PARTIAL | SEARCH | Build index, update doc, delete doc, filtered search |
| 10 | Website search | TODO | SEARCH | Website route search after SQLite migrate |
| 11 | Cache core API | PASS | CACHE | Automated primitive matrix |
| 12 | Client cache | PARTIAL | CACHE | Metadata invalidation tests |
| 13 | Sessions | TODO | CACHE | Browser login and API session round-trip |
| 14 | Rate limiting | PASS | CACHE | Rate-limit window expiry tests |
| 15 | Defaults/cache manager | PARTIAL | CACHE | Set/get defaults and clear cache |
| 16 | Scheduler | PASS | QUEUE | Enable scheduler in local mode and run one tick |
| 17 | Deferred inserts | PASS | QUEUE | Deferred insert + flush without Redis |
| 18 | Email queue | PASS | QUEUE | Queue email without SMTP send; flush in sync mode |
| 19 | Webhooks | TODO | QUEUE | Webhook enqueue after document save |
| 20 | Submission queue | TODO | QUEUE | Submit queued DocType with sync backend |
| 21 | Socket.IO Node server | TODO | QUEUE | Decide local WebSocket support vs disabled realtime |
| 22 | Permissions | TODO | DB | `get_list` with user permissions |
| 23 | Reports | TODO | DB | Standard report run on SQLite |
| 24 | Import/export | TODO | QUEUE | Data Import small CSV |
| 25 | Backups | PASS | DB | Backup and restore SQLite site |
| 26 | Tests/CI | PARTIAL | DB | Add SQLite-only test suite |

## Detailed DB/ORM Tracker Items

| # | Capability | Status | Worker | Acceptance Test |
| --- | --- | --- | --- | --- |
| 27 | Single DocTypes | PASS | DB | Read/write System Settings |
| 28 | Child tables | PASS | DB | Parent with child row insert/update/delete |
| 29 | `get_list` filters | PASS | DB | Operators: `=`, `!=`, `in`, `not in`, `like`, `between`, `is set`, `descendants of` |
| 30 | Joins (query builder) | TODO | DB | Email Queue join, permission joins, report joins |
| 31 | Aggregates/group/order | PASS | DB | count/sum/group_by/order_by/limit |
| 32 | DDL add/drop columns | GAP | DB | Customize Form add/drop fields |
| 33 | Indexes (DB section) | PARTIAL | DB | Unique/composite indexes |
| 34 | Fulltext equivalent | PARTIAL | DB | FTS build/query |
| 35 | Locking (DB section) | PARTIAL | DB | Document semantics and warnings |

## Detailed Cache Tracker Items

| # | Capability | Status | Worker | Acceptance Test |
| --- | --- | --- | --- | --- |
| 36 | Hash cache | PASS | CACHE | Session cache and translation cache |
| 37 | List cache | PASS | CACHE | Monitor/deferred/pulse tests |
| 38 | Set cache | PASS | CACHE | Changelog set tests |
| 39 | Expiry semantics | PARTIAL | CACHE | TTL expiration tests |
| 40 | Pattern matching | PASS | CACHE | Clear cache by pattern |
| 41 | Client cache metadata | PARTIAL | CACHE | Meta invalidation tests |
| 42 | Sessions (cache section) | TODO | CACHE | Browser login and reload |
| 43 | Rate limiter | PASS | CACHE | Abuse window expiry |

## Detailed Queue/Background Tracker Items

| # | Capability | Status | Worker | Acceptance Test |
| --- | --- | --- | --- | --- |
| 44 | `enqueue_after_commit` | PASS | QUEUE | Commit hook executes once |
| 45 | Deduplication/job status | GAP | QUEUE | Define unsupported behavior |
| 46 | `get_jobs()` | PARTIAL | QUEUE | Safe Exec and Auto Repeat behavior |
| 47 | Scheduler tick | PASS | QUEUE | Enable and run one scheduler tick |
| 48 | Deferred insert | PASS | QUEUE | Deferred insert then flush |
| 49 | Email queue | PASS | QUEUE | Create email queue, flush with SMTP disabled |
| 50 | Webhooks | TODO | QUEUE | Local HTTP receiver or mock |
| 51 | Submission queue | TODO | QUEUE | Submit queued DocType |
| 52 | Data import | TODO | QUEUE | Small CSV import |
| 53 | Print/PDF jobs | TODO | QUEUE | Generate PDF sync or clear unsupported |

## Detailed Realtime Tracker Items

| # | Capability | Status | Worker | Acceptance Test |
| --- | --- | --- | --- | --- |
| 54 | after_commit realtime | TODO | QUEUE | Save doc with notify update |
| 55 | Socket.IO server | N/A/TODO | QUEUE | Decide disabled vs local WebSocket |
| 56 | Desk client behavior without socket | TODO | QUEUE | Browser Desk smoke |
| 57 | Notifications | TODO | QUEUE | Create notification and check no error |
| 58 | Progress events | TODO | QUEUE | Long-running action UX decision |

## Detailed Search Tracker Items

| # | Capability | Status | Worker | Acceptance Test |
| --- | --- | --- | --- | --- |
| 59 | Legacy `__global_search` table | PARTIAL | SEARCH | `sync_global_search()` and search |
| 60 | SQLite FTS5 index | PARTIAL | SEARCH | Build/search/update/delete |
| 61 | Search rebuild after migrate | PARTIAL | SEARCH | Assert index contents after migrate |
| 62 | Query builder MATCH | GAP/PARTIAL | SEARCH | Define SQLite search API boundary |
| 63 | Website search | TODO | SEARCH | Search Web Page content |
| 64 | Permission-aware search | TODO | SEARCH | User-specific search result filtering |

## App Coverage Items

| # | Capability | Status | Worker | Acceptance Test |
| --- | --- | --- | --- | --- |
| 65 | ERPNext | TODO | DB/SEARCH | Install ERPNext app on SQLite site |
| 66 | HRMS/payments/other apps | TODO | DB/SEARCH | Install one at a time |
| 67 | Custom simple app | TODO | DB | Create app with parent/child DocTypes |
