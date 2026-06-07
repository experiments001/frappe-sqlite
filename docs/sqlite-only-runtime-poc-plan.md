# SQLite-Only Local Frappe Runtime POC Plan

## Objective

Implement a proof of concept that runs Frappe v16 locally with SQLite as the only database service, without requiring MariaDB, Redis, RQ workers, Node Socket.IO, or scheduler workers for the minimal web path.

This is not a browser/Pyodide project. `frappe-playground` is used only as evidence and inspiration:

- Frappe v16 can create a site with `bench new-site --db-type sqlite`.
- Frappe Desk can boot far enough when scheduler, async queue, realtime, and Redis are disabled or faked.
- Browser-specific pieces such as Pyodide, Service Worker routing, IndexedDB persistence, and iframe scoping are out of scope.

The POC should answer:

- Can a Frappe site boot with SQLite only?
- Can Administrator login?
- Can Desk load?
- Can basic DocType/document CRUD persist in SQLite?
- Which Redis uses are required for boot versus optional cache/queue/realtime behavior?
- Which source files need small patches to make this a deliberate supported local mode rather than a collection of hacks?

## Working Branch

Branch:

```text
poc/sqlite-only-runtime-plan
```

Base:

```text
version-16
5c16f12192 chore(release): Bumped to Version 16.20.0
```

## Dependency Classification

Use this classification while implementing and reporting failures.

```text
DB_REQUIRED
  Required for the SQLite POC. Must work.
  Examples: frappe.db.sql, get_doc, insert, save, schema sync, migrate.

CACHE_OPTIONAL
  Required for performance/cross-process sharing, but can degrade for single-process POC.
  Examples: metadata cache, boot cache, defaults cache, document cache.

QUEUE_OPTIONAL
  Not required for minimal web boot. Disable or execute synchronously.
  Examples: frappe.enqueue, scheduler jobs, email queue processing, long jobs.

REALTIME_OPTIONAL
  Not required for database/document API. No-op or disable initially.
  Examples: publish_realtime, Socket.IO, progress events, doc viewers.

SERVICE_IMPORT_ONLY
  Import exists but service may not be required for the tested path.
  Examples: redis module imports, MySQLdb imports in code paths not executed by SQLite.

UNSUPPORTED_FOR_POC
  Defer from initial POC.
  Examples: production background workers, Redis pubsub fanout, multi-process shared cache, high-write concurrency.
```

## External Reference: `frappe-playground`

Reference checkout:

```text
../frappe-playground
```

Key files:

- `Dockerfile.build`
- `public/config.js`
- `public/worker.js`
- `public/python/wsgi_server.py`
- `public/python/frappe_mocks.py`
- `public/sw.js`

Relevant lessons:

- `Dockerfile.build` creates Frappe v16 site with `bench new-site playground.local --db-type sqlite`.
- `Dockerfile.build` uses `bench init --skip-redis-config-generation`.
- `public/config.js` uses `db_type: "sqlite"` and disables async/scheduler-heavy behavior.
- `public/python/frappe_mocks.py` shows pressure points: Redis, RQ, MySQLdb imports, psutil, pwd/grp.
- `public/sw.js` mocks Socket.IO enough for Desk to settle.
- `public/worker.js` handles SQLite WAL checkpointing before copying DB state into IndexedDB. For local disk SQLite, this matters only for backup/export, not normal runtime.

Do not copy:

- Pyodide runtime.
- IndexedDB persistence.
- Service Worker request routing.
- Browser iframe scoping.
- COOP/COEP deployment requirements.

## Core File Map And Patch Ideas

### 1. Database Selection

File:

```text
frappe/database/__init__.py
```

Important anchors:

- `setup_database(...)`: dispatches database setup by `frappe.conf.db_type`.
- `bootstrap_database(...)`: dispatches bootstrap by `frappe.conf.db_type`.
- `drop_user_and_database(...)`: dispatches drop behavior by DB type.
- `get_db(...)`: returns `SQLiteDatabase` when `conf.db_type == "sqlite"`.

Patch idea:

- Add an explicit smoke assertion/helper for SQLite local mode rather than changing selection logic.
- Consider a small utility:

```python
def is_sqlite() -> bool:
    return frappe.local.conf.db_type == "sqlite"
```

Only add this if it removes repeated string checks during implementation.

Validation:

```python
import frappe
frappe.init(site="local.test", sites_path="sites")
frappe.connect()
assert frappe.conf.db_type == "sqlite"
assert frappe.db.db_type == "sqlite"
print(type(frappe.db))
```

### 2. SQLite Driver

File:

```text
frappe/database/sqlite/database.py
```

Important anchors:

- `SQLiteExceptionUtil`: maps sqlite3 exceptions to Frappe's expected DB error predicates.
- `SQLiteDatabase.get_connection`: creates connection and sets pragmas.
- `SQLiteDatabase.create_connection`: opens the `.db` file.
- `SQLiteDatabase.get_db_path`: resolves `site/db/<db_name>.db`.
- `SQLiteDatabase.setup_type_map`: maps Frappe field types to SQLite types.
- `SQLiteDatabase.escape`: string escaping.
- `_transform_query` and related helpers: SQL compatibility adaptation.

Observed behavior:

- WAL is already enabled.
- `synchronous=NORMAL` and `busy_timeout=5000` are already configured.
- Locking errors are mapped to deadlock/timeout style checks.

Patch ideas:

- Add clearer logging when SQLite opens a DB file path.
- Add a local runtime health method for POC diagnostics:

```python
def get_runtime_info(self):
    return {
        "db_type": self.db_type,
        "db_path": str(self.get_db_path()),
        "journal_mode": self.sql("PRAGMA journal_mode")[0][0],
        "busy_timeout": self.sql("PRAGMA busy_timeout")[0][0],
    }
```

- Avoid broad SQL behavior changes until a failing query proves the need.

Validation:

```bash
sqlite3 sites/local.test/db/*.db "PRAGMA journal_mode;"
sqlite3 sites/local.test/db/*.db ".tables"
```

### 3. Base Database API

File:

```text
frappe/database/database.py
```

Important anchors:

- `Database.__init__`: initializes `value_cache`, transaction callbacks, connection state.
- `Database.connect`: creates DB-API connection/cursor.
- `Database.sql`: central raw SQL execution path.
- `Database.get_value`: common single-value document API.
- `Database.get_values`: common multi-value document API.
- `Database.get_values_from_single`: reads `tabSingles`.
- `Database.set_single_value`: writes `tabSingles`.
- `Database.get_single_value`: reads Single DocType value with local cache.

Patch ideas:

- For POC instrumentation, add temporary debug logging around `Database.sql` behind a site config flag:

```json
{
  "sqlite_poc_trace_sql": 1
}
```

- Trace should print query type, db type, and truncated SQL.
- Do not leave noisy SQL tracing enabled by default.

Possible hook point:

```python
if frappe.conf.get("sqlite_poc_trace_sql"):
    self.logger.warning("SQLite SQL: %s", query[:500])
```

Validation:

- Confirm `frappe.db.get_value("User", "Administrator", "name")` works.
- Confirm `frappe.db.get_single_value("System Settings", "setup_complete")` works.
- Confirm simple insert/update/delete through Document API works.

### 4. Query Builder / ORM Query Layer

File:

```text
frappe/database/query.py
```

Important anchors:

- Query builder uses `frappe.local.qb`.
- `db_type = frappe.local.db.db_type`.
- Flags: `is_mariadb`, `is_postgres`, `is_sqlite`.
- Query builder applies filters, limits, offsets, `for_update`, group/order clauses.
- SQLite and MariaDB require a limit when offset is used.

Patch ideas:

- Add tests for common list queries under SQLite:
  - simple list.
  - filters.
  - `limit_start`/offset.
  - order by.
  - child-table join if used by Desk.
- Do not patch query builder unless a real list/report failure appears.

Validation commands:

```python
frappe.get_all("User", fields=["name"], limit=5)
frappe.get_list("DocType", filters={"custom": 0}, fields=["name"], limit_start=5, limit_page_length=5)
```

### 5. Schema / Migration Layer

File:

```text
frappe/database/sqlite/schema.py
```

Important anchors:

- `SQLiteTable.create`: creates DocType table and indexes.
- Child tables get `parent`, `parentfield`, `parenttype`.
- Autoincrement and UUID primary key handling exists.
- `SQLiteTable.alter`: handles add columns and table rebuild strategy.
- Index recreation follows table rebuild.
- Primary key alteration has explicit limits.

Patch ideas:

- Add POC tests for schema sync:
  - create a custom DocType.
  - add a Data field.
  - add an Int field.
  - add a child table.
  - run migrate.
  - verify records persist.
- Add warnings in limitation doc for schema operations SQLite cannot represent exactly.

Validation:

```bash
bench --site local.test migrate
sqlite3 sites/local.test/db/*.db "PRAGMA table_info('tabYour DocType');"
```

### 6. Document API

Files:

```text
frappe/model/document.py
frappe/model/base_document.py
frappe/client.py
frappe/desk/form/save.py
```

Important anchors:

`frappe/model/document.py`:

- `Document` class.
- `load_from_db`: loads normal and Single DocTypes.
- `FOR UPDATE` is skipped when `frappe.db.db_type == "sqlite"`.
- `load_children_from_db` and `_load_child_table_from_db`: child rows.
- `insert`: full insert lifecycle and hooks.
- `save` / `_save`: update lifecycle.
- `update_single`: writes Single DocTypes to `tabSingles`.

`frappe/model/base_document.py`:

- `db_insert`: builds raw `INSERT INTO tab{doctype}`.
- `db_update`: builds raw `UPDATE tab{doctype}`.
- `show_unique_validation_message`: has MariaDB-specific extraction logic.

`frappe/client.py`:

- REST-ish document API entrypoints: `insert`, `save`, `insert_doc`.

`frappe/desk/form/save.py`:

- Desk form save endpoint.

Patch ideas:

- No first-pass patches unless CRUD fails.
- Add POC test helpers that call both Python Document API and Desk form save path.
- If unique validation behaves poorly on SQLite, patch `show_unique_validation_message` to handle SQLite error strings cleanly.

Minimal CRUD smoke:

```python
doc = frappe.get_doc({
    "doctype": "ToDo",
    "description": "SQLite POC",
})
doc.insert()
frappe.db.commit()

loaded = frappe.get_doc("ToDo", doc.name)
loaded.description = "SQLite POC updated"
loaded.save()
frappe.db.commit()
```

Acceptance:

- Parent insert persists.
- Parent update persists.
- Child table insert/update persists for a custom DocType.
- Single DocType read/write works.

### 7. Cache Initialization

Files:

```text
frappe/__init__.py
frappe/utils/redis_wrapper.py
frappe/utils/caching.py
frappe/cache_manager.py
```

Important anchors:

`frappe/__init__.py`:

- `init`: loads site config, initializes local request cache/local cache, chooses query builder.
- `setup_redis_cache_connection`: creates `frappe.cache` and `frappe.client_cache`.

`frappe/utils/redis_wrapper.py`:

- Imports `redis`.
- `RedisWrapper(redis.Redis)` is the cache abstraction.
- `make_key`: prefixes keys by DB/site/user/shared.
- `set_value`: writes to `frappe.local.cache` and Redis.
- `get_value`: reads local cache, then Redis, then generator.
- `get_keys`, `delete_keys`, `delete_value`.
- Hash helpers: `hset`, `hget`, `hgetall`, `hdel`.

`frappe/utils/caching.py`:

- `request_cache`: request-local, no Redis.
- `site_cache`: process-local, no Redis.
- `redis_cache`: uses `frappe.cache`.

Patch ideas:

Add a deliberate local cache mode for SQLite POC:

```json
{
  "sqlite_only": 1,
  "cache_backend": "local"
}
```

Possible implementation:

- Add `LocalCacheWrapper` with a subset of `RedisWrapper` API.
- In `setup_redis_cache_connection`, if `frappe.conf.get("cache_backend") == "local"`, set:

```python
cache = LocalCacheWrapper()
client_cache = LocalClientCache()
```

Do not monkey-patch `redis` globally for the first implementation.

Required local cache API surface:

- `make_key`
- `set_value`
- `get_value`
- `delete_value`
- `delete_key`
- `delete_keys`
- `get_keys`
- `hset`
- `hget`
- `hgetall`
- `hdel`
- `exists`
- `expire`
- `setex`
- `incrby`

Acceptance:

- Frappe init/connect works with Redis stopped.
- Login and Desk boot do not require Redis.
- Metadata/document cache clear operations do not crash.

### 8. Queue / Background Jobs

File:

```text
frappe/utils/background_jobs.py
```

Important anchors:

- Imports `redis` and RQ classes directly.
- Queue names and timeouts are configured in `get_queues_timeout`.
- `enqueue` defaults `is_async=True`.
- `now=True` executes directly.
- `is_async=False` outside tests also executes directly, with deprecation warning.
- Redis queue connection failure only falls back during migrate.
- `enqueue_after_commit` registers on `frappe.db.after_commit`.
- `execute_job` handles worker lifecycle.

Patch ideas:

For POC, add a config-controlled synchronous queue mode:

```json
{
  "queue_backend": "sync"
}
```

Behavior:

- If `queue_backend == "sync"`:
  - `enqueue(..., enqueue_after_commit=False)` executes `frappe.call(method, **kwargs)`.
  - `enqueue(..., enqueue_after_commit=True)` registers direct execution in `frappe.db.after_commit`.
  - return a small `SyncJobResult` object or raw return value.

Keep this explicitly non-production.

Acceptance:

- Web boot does not import/start workers.
- Simple enqueue calls used during setup do not crash.
- Scheduled jobs remain paused unless explicitly tested.

### 9. Python Realtime

File:

```text
frappe/realtime.py
```

Important anchors:

- `publish_realtime`: central Python API.
- `after_commit` buffers realtime events on DB commit hooks.
- `emit_via_redis`: publishes to Redis channel `events`.
- `get_socketio_secret`: stores socket secret in Redis.
- `get_user_info`: called by Node Socket.IO auth.
- Room helpers: user, doc, doctype, site, task progress.

Patch ideas:

For POC:

```json
{
  "realtime_backend": "noop"
}
```

Behavior:

- `publish_realtime` records/debug-logs events or ignores them.
- `emit_via_redis` no-ops when backend is noop.
- `get_socketio_secret` returns a deterministic local secret or no-op only if Node realtime is tested.

Acceptance:

- Desk may show no realtime updates, but CRUD must work.
- No Redis pubsub required.
- Realtime limitations are documented.

### 10. Node Socket.IO Bridge

Files:

```text
realtime/index.js
realtime/middlewares/authenticate.js
node_utils.js
```

Important anchors:

`realtime/index.js`:

- Creates Socket.IO server.
- Uses namespace per site.
- Loads auth middleware.
- Subscribes to Redis `events`.
- Emits messages into socket rooms.

`realtime/middlewares/authenticate.js`:

- Reads `socketio_auth_secret` from Redis.
- Calls `/api/method/frappe.realtime.get_user_info`.
- Resolves site name from namespace/header/origin/default site.

`node_utils.js`:

- Loads bench/site config.
- Creates Redis subscriber using `@redis/client`.
- Supports env overrides for Redis and socket port.

Patch ideas:

- Do not run Node realtime for milestone 1.
- Later optional patch: if `realtime_backend == "local"` or `noop`, let Node start without Redis and skip pubsub subscription.
- Another option: no-op Socket.IO endpoint for Desk only, similar in spirit to `frappe-playground/public/sw.js`.

Acceptance:

- Milestone 1 can pass with Node realtime disabled.
- If browser console noise is excessive, document it or add a no-op endpoint in a later phase.

## Implementation Milestones

### Milestone 0: Baseline SQLite Site Creation

Goal:

Create a Frappe v16 site with SQLite and verify DB path.

Commands:

```bash
bench init --frappe-branch version-16 --skip-redis-config-generation sqlite-bench
cd sqlite-bench
bench new-site local.test --db-type sqlite --admin-password admin
```

Expected:

- `sites/local.test/db/*.db` exists.
- `sites/local.test/site_config.json` contains `db_type: sqlite`.
- No MariaDB server is required for DB creation.

### Milestone 1: Minimal Local Web Runtime

Goal:

Serve Frappe through Python WSGI with SQLite.

Patch/add:

```text
run_sqlite_frappe.py
```

Sketch:

```python
import os
from pathlib import Path

from werkzeug.serving import run_simple

BENCH_ROOT = Path(__file__).resolve().parent
SITES_PATH = BENCH_ROOT / "sites"
SITE_NAME = os.environ.get("FRAPPE_SITE", "local.test")

os.chdir(SITES_PATH)
os.environ.setdefault("SITES_PATH", str(SITES_PATH))
os.environ.setdefault("FRAPPE_SITE", SITE_NAME)

from frappe.app import application

if __name__ == "__main__":
    run_simple("127.0.0.1", 8000, application, use_debugger=True, use_reloader=False)
```

Acceptance:

- `/login` loads.
- Administrator login works.
- `/desk` loads or failure is classified.
- Redis and MariaDB are not running.

### Milestone 2: Local Cache Backend

Goal:

Make boot/login/Desk independent from Redis cache.

Patch candidates:

```text
frappe/__init__.py
frappe/utils/redis_wrapper.py
new: frappe/utils/local_cache.py
```

Patch approach:

- Add a config switch, e.g. `cache_backend: local`.
- Provide `LocalCacheWrapper`.
- Use it from `setup_redis_cache_connection`.
- Keep behavior isolated behind config.

Acceptance:

- `frappe.init` does not attempt Redis when local cache backend is selected.
- `frappe.clear_cache()` works enough for Desk.
- `frappe.get_cached_doc`, metadata cache, defaults cache do not crash.

### Milestone 3: Synchronous Queue Backend

Goal:

Avoid Redis/RQ for POC flows.

Patch candidates:

```text
frappe/utils/background_jobs.py
new: frappe/utils/sync_jobs.py
```

Patch approach:

- Add `queue_backend: sync`.
- In `enqueue`, before Redis queue creation, execute directly when sync backend is selected.
- Respect `enqueue_after_commit` by registering direct execution on `frappe.db.after_commit`.

Acceptance:

- Setup/login/Desk flows do not fail due to queue calls.
- A test `frappe.enqueue(method, now=False)` can execute synchronously under config.
- Scheduler remains disabled.

### Milestone 4: Realtime No-op Backend

Goal:

Avoid Redis pubsub and Node Socket.IO for minimal Desk.

Patch candidates:

```text
frappe/realtime.py
```

Patch approach:

- Add `realtime_backend: noop`.
- If noop, `publish_realtime` either stores events in local debug list or returns.
- Do not publish to Redis.

Acceptance:

- Calls to `frappe.publish_realtime` do not crash.
- Desk remains usable without realtime.
- Realtime explicitly documented unsupported.

### Milestone 5: CRUD Coverage

Goal:

Prove document API and Desk CRUD on SQLite.

Tests:

- Python Document API insert/save/load/delete.
- Single DocType read/write.
- Child table insert/save.
- Desk form save.
- List view query.
- Basic report/list query.

Patch candidates:

```text
frappe/tests/test_sqlite_only_runtime.py
```

Acceptance:

- All CRUD cases pass with Redis/MariaDB stopped.
- Failures are classified as DB compatibility, cache, queue, realtime, or unsupported.

### Milestone 6: Migration / Schema Coverage

Goal:

Prove DocType sync and simple migrations.

Tests:

- Create custom DocType.
- Add field.
- Add child table.
- Run migrate.
- Verify existing records persist.

Patch candidates:

```text
frappe/database/sqlite/schema.py
frappe/tests/test_sqlite_schema_sync.py
```

Acceptance:

- Simple schema changes work.
- Unsupported schema changes are documented.

### Milestone 7: Optional Realtime / Queue Expansion

Only after milestones 1-6:

- SQLite-backed queue table.
- Local websocket server without Redis.
- Durable cache table.
- Multi-process safety evaluation.

These are not part of minimal POC.

## Validation Commands

Check DB:

```bash
cat sites/local.test/site_config.json
ls -lah sites/local.test/db
sqlite3 sites/local.test/db/*.db ".tables"
sqlite3 sites/local.test/db/*.db "PRAGMA journal_mode;"
```

Check no services:

```bash
pgrep redis-server || true
pgrep mariadbd || true
pgrep mysqld || true
```

Run app:

```bash
python run_sqlite_frappe.py
```

HTTP:

```bash
curl -I http://127.0.0.1:8000/login
curl -I http://127.0.0.1:8000/desk
```

Python smoke:

```bash
bench --site local.test console
```

```python
import frappe
frappe.db.db_type
frappe.db.get_value("User", "Administrator", "name")
```

## Risks

### SQLite Compatibility

Raw SQL in Frappe or apps may assume MariaDB syntax. Query-builder-backed paths are safer than hand-written SQL.

### Concurrency

SQLite is suitable for single-user/local/low-write use. It is not a Redis/MariaDB replacement for horizontally scaled production workloads.

### Cache Semantics

In-process cache is not shared across workers. Keep milestone 1 single-process.

### Queue Semantics

Synchronous queue mode changes execution timing. Some jobs expect worker context or separate transactions.

### Realtime Semantics

No-op realtime removes progress events, doc viewers, live notifications, and socket broadcasts.

### Import Pressure

Some modules import Redis/RQ/MySQL clients directly. Distinguish import-only failures from actual service requirements.

## Deliverables For Implementation PR

Minimum:

```text
README_SQLITE_ONLY_RUNTIME.md
run_sqlite_frappe.py
frappe/utils/local_cache.py
frappe/utils/sync_jobs.py
tests or manual validation log
```

Possible source patches:

```text
frappe/__init__.py
frappe/utils/redis_wrapper.py
frappe/utils/background_jobs.py
frappe/realtime.py
```

Required documentation:

```text
SQLITE_ONLY_LIMITATIONS.md
```

The implementation must not claim full Frappe support. It should claim only the flows validated by commands/tests.

