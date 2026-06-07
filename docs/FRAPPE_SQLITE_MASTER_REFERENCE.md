# Frappe SQLite — Master Reference Document

**Branch:** `poc/sqlite-only-runtime-plan` → merged into `main`
**Date:** 2026-06-07
**Status:** Phase 1 COMPLETE · Phase 2 IN PROGRESS · Phase 3 (binary) PASSED · Phase 4 (Tauri) NEXT

---

## Table of Contents

1. [What This Is](#1-what-this-is)
2. [Repository Layout](#2-repository-layout)
3. [All Code Changes — Every File and Why](#3-all-code-changes--every-file-and-why)
4. [Tooling Stack — What We Use and How](#4-tooling-stack--what-we-use-and-how)
5. [Runtime Configuration Reference](#5-runtime-configuration-reference)
6. [Architecture Decisions](#6-architecture-decisions)
7. [Concurrency Model](#7-concurrency-model)
8. [Current Capability Status](#8-current-capability-status)
9. [Desktop Binary Packaging — Full Plan](#9-desktop-binary-packaging--full-plan)
10. [The `frappe-desktop` CLI Tool — Design and Roadmap](#10-the-frappe-desktop-cli-tool--design-and-roadmap)
11. ["Try on Desktop" Docker Pattern](#11-try-on-desktop-docker-pattern)
12. [App Lifecycle Management — Install, Update, Uninstall, Migrate](#12-app-lifecycle-management--install-update-uninstall-migrate)
13. [Site Management — Add, Remove, Clone, Export](#13-site-management--add-remove-clone-export)
14. [Further Development Roadmap](#14-further-development-roadmap)
15. [Brainstorm — New Ideas](#15-brainstorm--new-ideas)

---

## 1. What This Is

This repository (`experiments001/frappe-sqlite`, branch `poc/sqlite-only-runtime-plan`) proves that **Frappe v16 can run as a fully self-contained single-file application** — no MariaDB, no Redis, no RQ workers, no Node Socket.IO, no scheduler processes.

The goal is a desktop application that a non-developer can download, open, and use without installing any infrastructure. The backend is SQLite; everything else (cache, queue, realtime) runs in-process.

**What Phase 1 delivered:**
- Frappe core boots, migrates, serves Desk, and handles document CRUD with MariaDB and Redis containers stopped.
- 35/36 automated tests pass without any external services.
- A PyInstaller binary (≈32 MB) runs on macOS without Python installed.
- The Tauri native window phase is next.

**What this is NOT:**
- A replacement for MariaDB in production. MariaDB remains the default and correct choice for multi-user, multi-process, horizontally scaled deployments.
- A completed product. ERPNext compatibility is untested, schema alteration has a known blocker, sessions and permissions are only partially verified.

---

## 2. Repository Layout

```
frappe-sqlite/                     ← Frappe v16 fork (base: version-16, tag 16.20.0)
  frappe/
    __init__.py                    ← PATCHED: LocalCache wiring
    realtime.py                    ← PATCHED: noop backend gate
    locale.py                      ← PATCHED: bug fix (uninitialized variable)
    database/
      sqlite/
        database.py                ← PATCHED: core SQLite driver, most changes here
        schema.py                  ← PATCHED: DDL helpers
        setup_db.py                ← PATCHED: WAL pragma at site creation
    model/
      document.py                  ← PATCHED: for_update documented as no-op
    utils/
      background_jobs.py           ← PATCHED: sync queue backend
      redis_wrapper.py             ← PATCHED: LocalCache + LocalClientCache
    deferred_insert.py             ← PATCHED: bytes-to-string decode guard
    utils/global_search.py         ← PATCHED: SQLite SQL branch
    tests/
      test_sqlite_only_runtime.py  ← NEW: 36-test suite (no external services)
  tests_scratch/
    test_sqlite_rebuild_audit.py   ← NEW: adversarial DDL parser tests (throwaway)
  docs/
    BLOCKERS.md                    ← open issues
    DECISIONS.md                   ← architecture decisions log
    PROGRESS.md                    ← timestamped step log
    STATUS.md                      ← current phase and working/broken
    WORK_PLAN.md                   ← prioritized fix sequence
    SQLITE_ONLY_LIMITATIONS.md     ← intentional restrictions
    sqlite-production-readiness.md ← full gap/priority analysis
    sqlite-full-coverage-tracker.md← master capability matrix
    sqlite-only-runtime-poc-plan.md← original POC objective
    sqlite-first-design-review.md  ← design philosophy
    sqlite-concurrency-model.md    ← write locking semantics
    sqlite-backup-restore.md       ← backup/restore procedures
    sqlite-site-access.md          ← quick access guide
    frappe-sqlite-binary-app.md    ← Phase 0–5 packaging plan
    sqlite-only-runtime-agent-handoff.md ← env setup for agents
    status/PHASE1_STATUS.md        ← Phase 1 exit criteria
    status/PHASE2_STATUS.md        ← Phase 2 worker results
    FRAPPE_SQLITE_MASTER_REFERENCE.md ← THIS FILE
```

---

## 3. All Code Changes — Every File and Why

### 3.1 `frappe/database/sqlite/database.py` — Core SQLite Driver

This is where the most work happened. Every change is behind `db_type == "sqlite"` checks; MariaDB/Postgres paths are untouched.

#### Fix 1.2 — Native `RENAME COLUMN` + index preservation on table rebuild

**Problem:** The original table rebuild (required for SQLite since it cannot `ALTER COLUMN`) was a naive 5-step process that dropped indexes. Any field type change silently lost all indexes on the table.

**Fix:** Replaced with a 12-step procedure:
1. Read current `CREATE TABLE` SQL from `sqlite_master`
2. Parse column definitions
3. Patch the target column's type declaration
4. Rename old table to `_old_<name>`
5. Create new table with patched schema
6. `INSERT INTO new SELECT * FROM old`
7. Recreate all indexes from `sqlite_master` (filtered to this table)
8. Recreate all triggers from `sqlite_master` (filtered to this table)
9. Run `PRAGMA foreign_key_check`
10. Drop old table
11. Run `PRAGMA integrity_check` on new table
12. Commit

For `RENAME COLUMN`, SQLite 3.25+ supports `ALTER TABLE … RENAME COLUMN` natively — use that directly instead of a full rebuild.

#### Fix 1.2b — Full schema preservation in `change_column_type`

**Problem:** The original `change_column_type` built a new column definition string from scratch (`col_name TEXT NOT NULL DEFAULT ''`) — losing PRIMARY KEY, AUTOINCREMENT, CHECK constraints, and DEFAULT expressions.

**Fix:** Parse the original column definition from `sqlite_master`, surgically replace only the type token, keep everything else verbatim.

#### Fix 1.2c — Quote-aware `_split_create_table_body`

**Problem:** The parser that splits a `CREATE TABLE` body into individual column definitions was not quote-aware. Two cases broke it:
- `DEFAULT '('` — an open-paren inside a string literal incremented paren depth to 1, causing the next column's comma to be swallowed
- `"weird,col" TEXT` — a comma inside a double-quoted identifier triggered a split mid-identifier

**Fix:** `_split_create_table_body` now tracks `in_quote` state (`None | "'" | '"'`). While inside a quoted region: chars pass through unchanged, no paren depth change, no comma splits. Handles `''''` and `"""` escaped quotes. Paren depth and comma splits only happen outside quoted regions. All 8 adversarial test cases pass.

#### Fix 1.3 — Transactional DDL

**Problem:** `check_implicit_commit()` was guarding DDL operations, treating them as auto-committing like MariaDB. In SQLite, DDL is fully transactional — it participates in the active transaction and rolls back on failure.

**Fix:** Removed the `check_implicit_commit()` guard from the SQLite DDL path. Migrations now roll back atomically if any step fails.

#### Fix 1.4 — `for_update` documented as intentional no-op

**Problem:** `frappe/model/document.py` skips `FOR UPDATE` on SQLite. This looked like an oversight.

**Fix:** Added a comment explaining why this is safe: `BEGIN IMMEDIATE` acquires an exclusive write lock at transaction start, which is *more* exclusive than MariaDB's row-level `FOR UPDATE`. Once you hold the SQLite write lock, no other writer can enter a transaction at all. The no-op is correct by design.

#### Fix 2.2 — Native dict-value parameter binding

**Problem:** Frappe's query layer uses `%(name)s` style dict placeholders (MariaDB-style). The SQLite driver was converting these with string interpolation, creating both a SQL injection surface and a prepared-statement cache killer (every unique value produced a new statement).

**Fix:** Convert `%(name)s` → `:name` and use the native `sqlite3` binding with a dict. SQLite can cache the parameterized statement; the value never touches the SQL string.

#### Fix 2.4 — Remove Python `CONCAT_WS` UDF shim

**Problem:** A Python UDF registered `CONCAT_WS` because older SQLite versions lacked it.

**Fix:** SQLite 3.44+ (released November 2023) has native `CONCAT_WS`. Removed the UDF shim. The minimum SQLite version is now 3.44.

#### Fix 3.1 — PRAGMA performance profile

**Problem:** Default SQLite connection settings leave significant performance on the table for a local desktop workload.

**Fix:** Added a "server profile" applied once at connect time:
```sql
PRAGMA cache_size = -32768;        -- 32 MB page cache
PRAGMA mmap_size = 134217728;      -- 128 MB memory-mapped I/O
PRAGMA temp_store = MEMORY;        -- temp tables in RAM not disk
PRAGMA wal_autocheckpoint = 1000;  -- checkpoint every 1000 pages
PRAGMA foreign_keys = OFF;         -- app-level integrity (explicit decision)
```

#### Fix 4.1 — `BEGIN IMMEDIATE` for all write transactions

**Problem:** With `BEGIN` (deferred mode), two connections can both start a transaction, both read data, then both attempt their first write — only one succeeds; the other gets `SQLITE_BUSY` mid-transaction after already doing work.

**Fix:** `SQLiteDatabase.begin()` now issues `BEGIN IMMEDIATE`. The write lock is acquired up-front. The loser fails immediately at the `BEGIN` statement (before doing any work), waits `busy_timeout` ms, and retries cleanly.

#### Fix 4.2 — Single `_BUSY_TIMEOUT_MS` constant

**Problem:** The busy timeout was set in multiple places with different values.

**Fix:** Unified `_BUSY_TIMEOUT_MS = 5000` and `_CONNECT_TIMEOUT_S = 6` as single sources of truth in the class.

#### Fix 2.7 — `PRAGMA journal_mode=WAL` at site creation, not per-connection

**Problem:** WAL was being set on every connection open. This is redundant (WAL persists in the DB file header after the first set) and adds overhead.

**Fix:** Moved `PRAGMA journal_mode=WAL` to `setup_db.py` (site creation). It runs exactly once. Subsequent connections inherit WAL automatically.

---

### 3.2 `frappe/database/sqlite/schema.py` — DDL Helpers

Updated table alteration to:
- Use native `ALTER TABLE … RENAME COLUMN` (SQLite 3.25+) instead of full rebuild for simple renames
- Use native `ALTER TABLE … DROP COLUMN` (SQLite 3.35+) for drops
- Integrated full schema preservation logic from `database.py` for type changes

---

### 3.3 `frappe/database/sqlite/setup_db.py` — Site Bootstrap

Added `PRAGMA journal_mode=WAL` at site creation time (one-time, persistent). Previously this was done per-connection.

---

### 3.4 `frappe/utils/redis_wrapper.py` — In-Process Cache

Added two new classes used when `cache_backend = local`:

**`LocalCache`** — in-process replacement for Redis cache:
- Thread-safe `dict` + `threading.Timer` for TTL expiry
- Implements: `set_value`, `get_value`, `delete_value`, `delete_key`, `delete_keys`, `get_keys`, `hset`, `hget`, `hgetall`, `hdel`, `hkeys`, `hexists`, `lpush`, `lpop`, `rpush`, `rpop`, `llen`, `lrange`, `lindex`, `sadd`, `srem`, `sismember`, `smembers`, `spop`, `exists`, `expire`, `setex`, `incrby`, `delete`, `get`, `set`, `ping`
- Real TTL via `threading.Timer` (not a stub)
- Pattern-based `delete_keys` using `fnmatch`

**`LocalClientCache`** — in-process replacement for Redis client (metadata invalidation):
- Wraps `frappe.local.cache` dict
- Used for DocType metadata, defaults, and permission cache

**New methods added to existing `RedisWrapper`:**
- `delete()` — was missing, used by several callers
- `lindex()` — needed by telemetry/pulse client

---

### 3.5 `frappe/utils/background_jobs.py` — Sync Queue

Added `queue_backend = sync` config gate:
- `frappe.enqueue(method, **kwargs)` executes immediately in-process when sync mode is enabled
- `enqueue_after_commit=True` registers execution on `frappe.db.after_commit` (fires once after commit, cleared on rollback)
- Returns a thin `SyncJobResult` object so callers that check job status don't crash
- `get_jobs()` returns an empty map (no RQ registry in sync mode)

---

### 3.6 `frappe/realtime.py` — No-op Backend

Added `realtime_backend = noop` config gate:
- `publish_realtime()` returns immediately, no Redis pubsub
- `emit_via_redis()` returns immediately
- `get_socketio_secret()` uses site config value instead of Redis (no Redis lookup)
- After-commit realtime events are dropped silently

---

### 3.7 `frappe/__init__.py` — Cache Wiring

`setup_redis_cache_connection()` now checks `frappe.conf.get("cache_backend")`:
- If `"local"`: instantiates `LocalCache` and `LocalClientCache` instead of connecting to Redis
- If unset or `"redis"`: original Redis path unchanged

---

### 3.8 `frappe/model/document.py` — `for_update` Note

Added a comment at the `for_update` skip-on-sqlite path explaining why it is safe by design (see section 3.1 Fix 1.4 and section 7).

---

### 3.9 `frappe/locale.py` — Bug Fix

Fixed an uninitialized `value` local variable in `get_locale_value()`. This would raise `UnboundLocalError` in certain code paths. Unrelated to SQLite but found during testing.

---

### 3.10 `frappe/deferred_insert.py` — Bytes Decode Guard

Added a guard that decodes `bytes` values to `str` before storing in the deferred insert buffer. Without this, the JSON serialization of the buffer fails when binary data appears.

---

### 3.11 `frappe/utils/global_search.py` — SQLite SQL Branch

Added a SQLite-aware SQL branch for global search indexing. MariaDB uses `INSERT IGNORE`; SQLite uses `INSERT OR IGNORE` (different syntax for the same semantics).

---

### 3.12 `frappe/tests/test_sqlite_only_runtime.py` — New Test Suite (36 tests)

Complete test coverage for the SQLite-only runtime profile, all running with MariaDB and Redis stopped.

**TestSQLiteOnlyRuntime (12 tests):**
- `test_runtime_backends` — assert `db_type`, `cache_backend`, `queue_backend`, `realtime_backend`
- `test_local_cache` — hash/list/set primitive smoke
- `test_local_cache_ttl` — real TTL expiry via `setex` / `expire`
- `test_metadata_and_defaults_cache` — metadata read after cache clear
- `test_sync_enqueue` — synchronous job execution with args/kwargs
- `test_sync_enqueue_after_commit` — register execution on commit hook
- `test_after_commit_reset_on_rollback` — commit callback cleared after rollback
- `test_noop_realtime` — realtime returns cleanly without Redis
- `test_publish_realtime_noop` — publish no-op after commit
- `test_sync_enqueue_feature_gate` — RQ queue fails gracefully in sync mode
- `test_scheduler_paused_gate` — scheduler early-return verified
- `test_todo_crud_and_filters` — document CRUD and list filters

**TestSQLiteBackupRestore (3 tests):**
- DB file exists, offline copy works, `PRAGMA integrity_check` passes

**TestSQLiteDBCoverage (7 tests, 1 skipped):**
- Single DocType read/write, child table CRUD, all filter operators, aggregates, savepoints, `for_update` no-op
- SKIPPED: schema add/drop field (known blocker: `ImplicitCommitError`)

**TestSQLiteCacheCoverage (8 tests):**
- All cache primitive types, real TTL expiry, pattern delete, rate limiter, session persistence

**TestSQLiteQueueCoverage (6 tests):**
- Enqueue with args/kwargs, after-commit fires, deferred insert, email queue create, scheduler tick noop, no Redis access

---

### 3.13 `tests_scratch/test_sqlite_rebuild_audit.py` — Adversarial DDL Audit

8 adversarial edge cases for `_split_create_table_body`:
- `CHECK` with comma in string literal
- `DEFAULT '('` (unbalanced paren in string)
- Composite `PRIMARY KEY`
- `INTEGER PRIMARY KEY AUTOINCREMENT`
- Generated column (`GENERATED ALWAYS AS`)
- Quoted identifier `"weird,col"`
- `CHECK` with nested parens
- `DEFAULT` expression (`julianday('now')`)

All 8 pass after fix 1.2c. This file is marked throwaway (not shipped in production).

---

## 4. Tooling Stack — What We Use and How

### 4.1 SQLite 3.44+ (Python `sqlite3` stdlib module)

**What:** The embedded relational database. No server, no network, no installation.

**How we use it:**
- `sqlite3.connect(path, timeout=6.0)` — opens the `.db` file
- `BEGIN IMMEDIATE` — exclusive write lock at transaction start (not the default `BEGIN DEFERRED`)
- `PRAGMA journal_mode = WAL` — write-ahead log for concurrent readers during writes
- `PRAGMA busy_timeout = 5000` — retry write-lock acquisition for 5 seconds before raising
- `PRAGMA cache_size = -32768` — 32 MB in-memory page cache
- `PRAGMA mmap_size = 134217728` — 128 MB memory-mapped I/O for read performance
- `PRAGMA temp_store = MEMORY` — temp tables in RAM
- `PRAGMA wal_autocheckpoint = 1000` — checkpoint WAL every 1000 pages
- `sqlite_master` — introspect existing table schema for rebuild operations
- SQLite 3.25+ native `ALTER TABLE … RENAME COLUMN`
- SQLite 3.35+ native `ALTER TABLE … DROP COLUMN`
- SQLite 3.44+ native `CONCAT_WS`

**Version minimum:** SQLite 3.44 (November 2023). macOS ships SQLite 3.43 on Ventura but 3.45+ on Sonoma. Linux distros typically have 3.40+ in 2024 packages.

---

### 4.2 Python `threading` (stdlib)

**What:** Thread safety for the in-process cache.

**How we use it:**
- `threading.Lock()` — guards all reads and writes to `LocalCache._store`
- `threading.Timer(ttl, callback)` — fires TTL expiry without a background thread loop
- Each key's TTL cancels the previous timer and starts a new one on `setex`/`expire`

---

### 4.3 Werkzeug `run_simple`

**What:** WSGI dev server, used in the desktop binary runner.

**How we use it:**
- `run_simple("127.0.0.1", port, application, use_reloader=False, threaded=True)`
- `threaded=True` gives each request its own thread — fine for local single-user
- Bound to `127.0.0.1` only, never `0.0.0.0`
- Production deployments should use gunicorn

---

### 4.4 PyInstaller

**What:** Freezes a Python application + all dependencies into a standalone directory that runs without Python installed.

**How we use it:**
- `--onedir` mode: produces a folder (`dist/frappe-sqlite-macos/`) rather than a single file (faster startup, easier debugging)
- Custom hooks `hook-frappe.py` and `hook-erpnext.py` use `collect_all()` to pull in all templates, fixtures, and dynamic imports
- `collect_submodules("passlib.handlers")` — passlib dynamically imports hash handlers; must be collected explicitly
- Assets (`sites/assets/`) bundled twice: once as `sites/assets` (seed site) and once as `assets` (for `get_assets_json()` resolution)
- `hiddenimports` list for dynamic imports PyInstaller cannot detect statically
- `excludes = ["tkinter", "pytest", "IPython"]` to trim binary size

**Build runs on the host machine** (must match target architecture: arm64 or x86_64). Cannot cross-compile.

**Fallback:** Nuitka — if PyInstaller becomes unworkable for a specific app's dependency graph, Nuitka compiles Python to C and produces a standalone binary. Slower build, faster runtime, better compatibility with some packages.

---

### 4.5 Tauri (planned, Phase 4)

**What:** Rust-based native desktop app framework that wraps a WebView. Much smaller than Electron.

**How we use it:**
- PyInstaller binary runs as a **sidecar** process managed by Tauri
- Tauri opens a native window, polls the sidecar's HTTP healthcheck, then loads `http://127.0.0.1:<port>` in the WebView
- User sees a native macOS window — no browser, no URL bar, no developer tools visible
- Tauri handles: window lifecycle, app menu, auto-updater, code signing, DMG generation
- No Frappe logic in Rust — Tauri is shell-only

**Key Tauri plugins needed:**
- `tauri-plugin-shell` — spawn and manage the sidecar process
- `tauri-plugin-updater` — auto-update from Cloudflare R2 / S3

---

### 4.6 Docker (development environment)

**What:** The development environment where bench and all build steps run before being exported to the host Mac for PyInstaller.

**How we use it:**
- `devcontainer-frappe-1` container with Frappe bench at `/workspace/development/sqlitepoc`
- `bench new-site sqliteonly.localhost --db-type sqlite` — creates the SQLite site
- `bench build` — builds frontend assets (requires Node, npm; done inside Docker)
- `docker cp` — exports `apps/`, `sites/`, `desktop_runtime/` to host Mac for PyInstaller
- Bind mount means files are shared between container and host at `/Users/safwan/Code/docker/fdocker/development/`

---

### 4.7 `bench` CLI (Frappe's own tooling)

**What:** Frappe's project manager — creates sites, runs migrations, builds assets, starts servers.

**How we use it during development:**
- `bench new-site --db-type sqlite` — creates SQLite site
- `bench --site <name> migrate` — syncs DocType schemas to SQLite tables
- `bench --site <name> clear-cache` — clears all in-process caches
- `bench serve` — starts Werkzeug dev server (we replace this with the desktop runner)
- `bench build` — builds JS/CSS assets

**What we replace in the binary:** We do NOT include bench in the binary. The desktop runner (`desktop_runtime/runner/main.py`) replaces `bench serve` with a direct call to `frappe.app.application`.

---

### 4.8 `pytest` + `frappe.tests` framework

**What:** Test runner for the 36-test SQLite suite.

**How we use it:**
- Tests run against a live SQLite site with all external services stopped
- `frappe.init` + `frappe.connect` bootstraps Frappe in test mode
- Teardown uses `frappe.destroy()` and explicit document cleanup
- `unittest.skip` marks the one known blocker (schema alteration)

---

## 5. Runtime Configuration Reference

The four config keys that switch Frappe into SQLite-only local mode. All go in `sites/<site>/site_config.json`.

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

| Key | Value | Effect |
|-----|-------|--------|
| `db_type` | `"sqlite"` | Use `SQLiteDatabase` instead of `MariaDBDatabase` |
| `cache_backend` | `"local"` | Use `LocalCache` (in-process) instead of Redis |
| `queue_backend` | `"sync"` | Execute `frappe.enqueue()` calls immediately in-process |
| `realtime_backend` | `"noop"` | No-op all `publish_realtime()` calls |
| `pause_scheduler` | `1` | Skip scheduler tick (return early from `start_scheduler`) |
| `disable_async` | `1` | Frappe internal flag to disable async behavior |

**None of these keys affect MariaDB sites.** Each is checked at the call site with `frappe.conf.get(key)`. MariaDB and Postgres paths are unchanged.

---

## 6. Architecture Decisions

Full decision log: `docs/DECISIONS.md`. Summary of the most important ones:

### Decision 1: SQLite-First vs MariaDB-Emulation

**Rejected:** Emulate every MariaDB behavior for SQLite (keep auto-committing DDL semantics, use Python UDFs for missing SQL functions, etc.).

**Chosen:** Lean on SQLite's actual strengths. SQLite has transactional DDL, fast prepared statements with native binding, WAL for concurrent reads, and a self-contained file format. Use these strengths rather than emulating MariaDB.

**Impact:** Removed the `CONCAT_WS` UDF shim (use native), removed `check_implicit_commit()` guard (DDL is transactional in SQLite), use native dict binding (`%()s` → `:name`).

### Decision 2: `for_update` is a no-op by design

`frappe/model/document.py` skips `FOR UPDATE` on SQLite. This is intentional. `BEGIN IMMEDIATE` acquires the write lock at transaction start — no other writer can touch any row until commit. This is strictly more exclusive than row-level `FOR UPDATE` in MariaDB. The no-op is safe within the single-writer envelope.

### Decision 3: `foreign_keys = OFF` by design

SQLite's `PRAGMA foreign_keys` is `OFF` by default. We leave it off. Frappe enforces referential integrity at the application layer (Link fields, delete behavior). Turning on `foreign_keys` would cause migrations to fail on the existing schema because FK constraints are not declared in a form SQLite can verify.

### Decision 4: Money stored as `REAL` (IEEE-754) — **UNRESOLVED**

SQLite has no `DECIMAL` type. Currency fields currently land as `REAL` (IEEE-754 float). This silently accumulates rounding error in multi-currency/VAT scenarios. This is a product decision, not a technical one. Options:
- Store as integer minor units (cents/paise) — requires schema + UI changes
- Store as `TEXT` and parse with Python `Decimal` — safe but slow for aggregates
- Document as explicit limitation for non-financial sites

**Current status:** Not resolved. Sites with financial data should not use SQLite until this is decided.

### Decision 5: Single-writer envelope

The safe deployment for SQLite is 1 write-worker process (or 2–4 with `BEGIN IMMEDIATE` + `busy_timeout = 5s` for low-write workloads). High write throughput requires either a write queue routing all writes through one worker, or migration to MariaDB.

### Decision 6: Assets duplication in PyInstaller

`frappe.get_assets_json()` calls `frappe.read_file("assets/assets.json")` relative to `cwd`. The actual assets live in `sites/assets/`. In the frozen binary, we bundle `sites/assets` twice — once as `sites/assets` and once as `assets` — so both code paths work without patching Frappe.

---

## 7. Concurrency Model

Full document: `docs/sqlite-concurrency-model.md`.

SQLite WAL gives **many concurrent readers + exactly one writer at a time**.

```
Readers: unlimited concurrent (WAL readers never block writers)
Writers: exactly one (WAL file-level write lock)
```

**`BEGIN IMMEDIATE`** (fix 4.1): acquires the write lock at transaction start, not at first write. This is critical. Without it:
1. Worker A: `BEGIN` → reads → starts writing → gets write lock
2. Worker B: `BEGIN` → reads → starts writing → `SQLITE_BUSY` mid-transaction

With `BEGIN IMMEDIATE`:
1. Worker A: `BEGIN IMMEDIATE` → gets write lock → reads → writes → commits
2. Worker B: `BEGIN IMMEDIATE` → waits up to 5s → retries → gets lock → ...

**Timeout chain:**

| Layer | Value | Purpose |
|-------|-------|---------|
| `PRAGMA busy_timeout` | 5 000 ms | SQLite retries write-lock before `OperationalError` |
| Python `timeout=` | 6 s | OS-level outer timeout, slightly higher so SQLite fires first |

**Safe deployment envelope:**

| Deployment | Workers | Notes |
|-----------|---------|-------|
| Desktop app (single user) | 1 | Zero contention |
| Small team / internal | 1–3 gunicorn | `BEGIN IMMEDIATE` absorbs bursts |
| Medium load (<50 users) | 2–4 gunicorn | Monitor WAL size |
| High write throughput | **1 + write queue** | Route writes through one worker |
| Multi-host / multi-region | ❌ | Not supported — SQLite is single-file |

---

## 8. Current Capability Status

**Test results:** 35/36 passing (1 SKIP: schema alteration)

**Legend:** ✅ PASS · ⚠️ PARTIAL · ❌ GAP · 🔲 TODO · — N/A

| Capability | Status | Notes |
|-----------|--------|-------|
| Site creation + migrate | ✅ | `bench new-site --db-type sqlite` + `bench migrate` |
| DB connection | ✅ | WAL, `BEGIN IMMEDIATE`, PRAGMA profile |
| Document CRUD | ✅ | insert, save, load, delete |
| Single DocType read/write | ✅ | `tabSingles` |
| Child table CRUD | ✅ | Parent + child rows |
| Query filters | ✅ | `=`, `!=`, `in`, `not in`, `like`, `between`, `is set`, `descendants of` |
| Aggregates | ✅ | count, sum, group_by, order_by, limit |
| Savepoints | ✅ | Nested transaction/savepoint |
| `for_update` | ✅ | No-op by design; safe under `BEGIN IMMEDIATE` |
| Backup/restore | ✅ | File copy + `PRAGMA integrity_check` |
| Local cache (all primitives) | ✅ | Hash, list, set, TTL, pattern delete |
| Rate limiter | ✅ | Window expiry |
| Sync enqueue | ✅ | `frappe.enqueue()` executes in-process |
| `enqueue_after_commit` | ✅ | Fires once after commit, cleared on rollback |
| Deferred insert | ✅ | `deferred_insert` + `save_to_db` flush |
| Email queue create | ✅ | Email Queue document insert |
| Scheduler (paused) | ✅ | Early return with `pause_scheduler=1` |
| Realtime no-op | ✅ | `publish_realtime()` returns silently |
| Desk boot (browser) | ✅ | Login page, Desk shell, List View, Form View (manually verified) |
| Joins | ⚠️ | Query builder emits correct SQL; app-level joins unverified |
| Indexes | ⚠️ | Migration passed; unique/composite variants unverified |
| Transactions (edge cases) | ⚠️ | Commit/rollback basic paths work; savepoint edges unverified |
| Global search | ⚠️ | SQLite branch exists; not runtime-tested |
| SQLite FTS5 | ⚠️ | Dedicated module + tests exist; integration unverified |
| Client cache invalidation | ⚠️ | Metadata reads work; full invalidation cycle unverified |
| Schema alteration | ❌ | `ImplicitCommitError` blocks ADD/DROP COLUMN — open GAP |
| Sessions | 🔲 | Login page renders; full session round-trip not tested |
| Permissions | 🔲 | Administrator works; non-admin user filters untested |
| Reports | 🔲 | Not tested |
| Webhooks | 🔲 | Likely sync via `enqueue_after_commit`; untested |
| Data import | 🔲 | Not tested |
| ERPNext | 🔲 | Not installed; untested |
| Money/DECIMAL | ❌ | Stored as IEEE-754 float; product decision needed |

---

## 9. Desktop Binary Packaging — Full Plan

Full document: `docs/frappe-sqlite-binary-app.md`.

**Current status (as of 2026-06-07):** Phase 3 PASSED. Binary runs on macOS without Python.

### Phase 0 — Verify Docker bench (DONE)
Confirmed `bench serve` works with SQLite site `sqliteonly.localhost` inside `devcontainer-frappe-1`.

### Phase 1 — Python source runner (DONE)

Created `desktop_runtime/runner/`:

```
desktop_runtime/runner/
  runtime_paths.py   # path resolution: bundle root, app data dir, sites path, logs path
  migration.py       # seed site on first launch (copy from bundle to ~/Library/...)
  server.py          # configure Python paths + env, find free port, start Werkzeug
  main.py            # CLI entry point: argparse, open browser, call serve()
```

Key design decisions:
- **Data is NOT in the bundle.** User data lives in `~/Library/Application Support/FrappeSQLite/` (macOS) or `~/.local/share/FrappeSQLite/` (Linux).
- **Seed site is in the bundle.** On first launch, `migration.py` copies the bundled seed site to the user data directory.
- **Port is dynamic.** `find_free_port()` scans `8765–8865` for an available port. No hardcoded port.
- **Browser opens automatically.** `threading.Timer(2, webbrowser.open)` after server starts.
- **`ERPNEXT_SQLITE_DATA_DIR` override** for testing and CI.

### Phase 2 — PyInstaller build (DONE)

Key spec decisions:
- `collect_all("frappe")` and `collect_all("erpnext")` — templates, fixtures, dynamic imports
- `collect_submodules("passlib.handlers")` — passlib's dynamic handler discovery
- Assets bundled twice (see Decision 6)
- `apps_txt` added to seed site bundle
- Build runs on host Mac (must match target CPU architecture)
- `excludes = ["tkinter", "pytest", "IPython"]` to trim size

Binary size: ≈32 MB executable

### Phase 3 — Smoke test (DONE)

Automated `smoke_test_macos.sh`:
1. Start binary with `ERPNEXT_SQLITE_DATA_DIR` pointing to a temp directory
2. Poll `http://127.0.0.1:8765` for HTTP 200
3. Login via API as Administrator
4. Create a ToDo
5. Kill binary, restart, confirm ToDo still in DB
6. Assert no MariaDB or Redis processes

All criteria passed.

### Phase 4 — Tauri shell (NEXT)

Architecture:
```
Tauri .app
  ├── sidecar: frappe-sqlite (Phase 2 binary)
  ├── Tauri spawns sidecar, polls HEAD http://127.0.0.1:<port>
  ├── WebView loads http://127.0.0.1:<port>
  └── Native window, native menu, no URL bar visible to user
```

Steps:
1. `npm create tauri-app@latest` in `desktop_shell/`
2. Copy Phase 2 binary as `src-tauri/binaries/frappe-sqlite-aarch64-apple-darwin`
3. `tauri.conf.json`: `"externalBin": ["binaries/frappe-sqlite"]`
4. `npm run tauri add shell` — plugin for sidecar lifecycle
5. Frontend `main.ts`: spawn sidecar → poll healthcheck → `window.location.href = url`
6. `npm run tauri build` → `.app` + `.dmg`

### Phase 5 — Signing, notarisation, updater (DEFERRED)

```
Code signing:   codesign + xcrun notarytool
Distribution:  .dmg with embedded .app
Updater:       tauri-plugin-updater, latest.json on Cloudflare R2
Update flow:   check → download signed DMG → backup SQLite DB → migrate → restart
Backup path:   ~/Library/Application Support/FrappeSQLite/backups/pre-update-<ver>-<ts>.sqlite
```

---

## 10. The `frappe-desktop` CLI Tool — Design and Roadmap

### 10.1 Vision

A single command-line tool that can turn **any Frappe app** into a desktop binary with minimal effort:

```bash
frappe-desktop build --app erpnext --out dist/
frappe-desktop run
frappe-desktop app install hrms
frappe-desktop app update frappe erpnext
frappe-desktop site new mysite
frappe-desktop site list
frappe-desktop migrate
```

This is the `docker build` moment for Frappe desktop apps. Any developer who has a working Frappe app should be able to produce a distributable desktop binary with one command.

### 10.2 Tool Structure

```
frappe-desktop/                    ← new repo or frappe-desktop PyPI package
  pyproject.toml
  frappe_desktop/
    __init__.py
    cli.py                         ← click/typer entrypoint
    commands/
      build.py                     ← build desktop binary (PyInstaller/Nuitka)
      run.py                       ← run the desktop app locally
      app.py                       ← install / update / uninstall apps
      site.py                      ← create / delete / list / clone sites
      migrate.py                   ← run migrations
      backup.py                    ← backup and restore
      shell.py                     ← open bench console
    core/
      bench_detect.py              ← auto-detect bench root
      pyinstaller_gen.py           ← generate .spec from app list
      seed_builder.py              ← build seed site for bundling
      runtime_paths.py             ← cross-platform data dir resolution
      migration.py                 ← first-launch seed copy
      server.py                    ← Werkzeug server wrapper
    platforms/
      macos.py                     ← macOS-specific paths, signing, notarization
      linux.py                     ← Linux AppImage / Flatpak
      windows.py                   ← Windows MSI (future)
```

### 10.3 `frappe-desktop build` Command

```bash
frappe-desktop build \
  --apps frappe,erpnext,hrms \      # comma-separated app list
  --site site1.local \              # which site to bundle as seed
  --platform macos-arm64 \         # target platform
  --product-name "My ERPNext" \    # display name
  --out dist/
```

What it does:
1. Auto-detects bench root (looks for `apps/` + `sites/` in cwd and parents)
2. Generates PyInstaller `.spec` from app list
3. Builds frontend assets (`bench build`) — can skip with `--skip-assets`
4. Creates seed site backup (WAL checkpoint + file copy of the site)
5. Runs PyInstaller
6. Produces `dist/<product-name>-<platform>/` directory

**For CI/CD:** `frappe-desktop build --no-browser-open --port 0` produces a binary that selects a port at runtime. The CI step exports the binary as an artifact.

### 10.4 `frappe-desktop app install` Command

```bash
frappe-desktop app install hrms --site mysite
frappe-desktop app install https://github.com/frappe/hrms --branch develop
```

What it does:
1. `git clone` (or `git pull` if already cloned) the app into `apps/`
2. `pip install -e apps/<app>`
3. `bench --site <site> install-app <app>`
4. `bench --site <site> migrate`
5. Rebuilds PyInstaller binary (or marks binary as stale and prompts rebuild)

**For embedded mode (binary already running):**
- The app download and pip install run in a background thread
- Binary stops, new binary is built with updated app, binary restarts
- User sees a "Updating — please wait" screen in the WebView during rebuild

### 10.5 `frappe-desktop app update` Command

```bash
frappe-desktop app update frappe erpnext    # update specific apps
frappe-desktop app update --all             # update all apps
```

What it does:
1. For each app: `git pull origin <branch>`
2. `pip install -e apps/<app>` (in case `pyproject.toml` changed)
3. `bench --site <site> migrate`
4. Rebuild binary (or prompt user to rebuild)
5. Pre-update backup: `frappe-desktop backup --pre-update-tag <old-version>`

**Rollback:** `frappe-desktop app rollback <app> --to <commit-hash>`

### 10.6 `frappe-desktop migrate` Command

```bash
frappe-desktop migrate                     # all sites
frappe-desktop migrate --site mysite
frappe-desktop migrate --dry-run           # show what would change
```

Always creates a pre-migration backup:
```
~/FrappeSQLite/backups/pre-migrate-<timestamp>.sqlite
```

### 10.7 `frappe-desktop site new` Command

```bash
frappe-desktop site new mysite \
  --admin-password secret \
  --apps frappe,erpnext
```

What it does:
1. `bench new-site <name> --db-type sqlite --admin-password <pw>`
2. For each app: `bench --site <name> install-app <app>`
3. `bench --site <name> migrate`
4. Updates `sites/apps.txt` and seed bundle

### 10.8 `frappe-desktop site list` / `site clone` / `site export`

```bash
frappe-desktop site list
frappe-desktop site clone mysite mysite-dev
frappe-desktop site export mysite --out mysite-backup.tar.gz
frappe-desktop site import mysite-backup.tar.gz --as newsite
```

Clone: copy SQLite `.db` file + `site_config.json` + `private/files/`. Checkpoint WAL first.
Export: tar.gz of site dir, WAL checkpointed.
Import: extract tar.gz, run migrate.

---

## 11. "Try on Desktop" Docker Pattern

### 11.1 The Problem

Any Frappe app project (ERPNext, HRMS, a custom app) should be able to offer a "Try on Desktop" button on its README or website. Clicking it downloads and runs the app locally without any developer tooling.

The pattern is: **add a `docker/desktop/` directory to any Frappe app repo** and the CI builds a desktop binary automatically.

### 11.2 Directory Structure to Add to Any Frappe App Repo

```
<your-frappe-app>/
  docker/
    desktop/
      README.md                    ← "How to build desktop binary for this app"
      docker-compose.yml           ← build environment
      Dockerfile.build             ← builds the binary inside container
      build.sh                     ← entrypoint: bench setup + PyInstaller
      spec/
        app_sqlite.spec.template   ← PyInstaller spec template (app-specific)
      hooks/
        hook-<appname>.py          ← PyInstaller hook for this app
      seed/
        site_config.json           ← SQLite site config template
        common_site_config.json    ← bench config with sqlite/local/sync/noop
```

### 11.3 `docker-compose.yml`

```yaml
version: "3.9"
services:
  builder:
    build:
      context: .
      dockerfile: Dockerfile.build
    volumes:
      - ../../:/app/apps/${APP_NAME}          # mount this app's source
      - ./dist:/output                         # build artefact goes here
    environment:
      - APP_NAME=${APP_NAME:-myapp}
      - FRAPPE_BRANCH=${FRAPPE_BRANCH:-version-16}
      - PLATFORM=${PLATFORM:-linux-x86_64}
```

### 11.4 `Dockerfile.build`

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    git curl nodejs npm \
    libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /bench

# Install bench
RUN pip install frappe-bench

# Init bench with SQLite-patched frappe
ARG FRAPPE_BRANCH=version-16
RUN bench init frappe-bench \
      --frappe-branch ${FRAPPE_BRANCH} \
      --skip-redis-config-generation \
      --skip-assets

WORKDIR /bench/frappe-bench

# Install the app being packaged
COPY . apps/${APP_NAME}/
RUN pip install -e apps/${APP_NAME}
RUN bench new-site desktop.local \
      --db-type sqlite \
      --admin-password admin \
      --install-app frappe \
      --install-app ${APP_NAME}

# Patch site config for local mode
RUN python -c "
import json, pathlib
p = pathlib.Path('sites/desktop.local/site_config.json')
c = json.loads(p.read_text())
c.update({
    'cache_backend': 'local',
    'queue_backend': 'sync',
    'realtime_backend': 'noop',
    'pause_scheduler': 1,
    'disable_async': 1,
})
p.write_text(json.dumps(c, indent=2))
"

# Build assets
RUN bench build

# Migrate
RUN bench --site desktop.local migrate

# Install PyInstaller
RUN pip install pyinstaller

# Copy desktop runtime + spec
COPY docker/desktop/spec/ desktop_runtime/
COPY docker/desktop/hooks/ desktop_runtime/hooks/

# Build
RUN pyinstaller desktop_runtime/${APP_NAME}_sqlite.spec --clean --noconfirm

# Export
RUN cp -r dist/${APP_NAME}-desktop/ /output/
```

### 11.5 `build.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

APP_NAME=${1:-myapp}
PLATFORM=${PLATFORM:-linux-x86_64}

cd "$(dirname "$0")/../.."   # project root

echo "Building desktop binary for: $APP_NAME ($PLATFORM)"

docker compose -f docker/desktop/docker-compose.yml \
  run --rm \
  -e APP_NAME="$APP_NAME" \
  -e PLATFORM="$PLATFORM" \
  builder

echo "Binary available at: docker/desktop/dist/$APP_NAME-desktop/"
echo "Run it: ./docker/desktop/dist/$APP_NAME-desktop/$APP_NAME-sqlite"
```

### 11.6 GitHub Actions CI Integration

Add to `.github/workflows/desktop-build.yml`:

```yaml
name: Desktop Build

on:
  push:
    tags: ['v*']
  workflow_dispatch:
    inputs:
      platform:
        type: choice
        options: [linux-x86_64, macos-arm64, macos-x86_64]

jobs:
  build:
    runs-on: ${{ matrix.runner }}
    strategy:
      matrix:
        include:
          - platform: linux-x86_64
            runner: ubuntu-latest
          - platform: macos-arm64
            runner: macos-latest

    steps:
      - uses: actions/checkout@v4

      - name: Build desktop binary
        run: |
          cd docker/desktop
          PLATFORM=${{ matrix.platform }} ./build.sh ${{ github.event.repository.name }}

      - name: Upload artefact
        uses: actions/upload-artifact@v4
        with:
          name: desktop-${{ matrix.platform }}
          path: docker/desktop/dist/

      - name: Upload to release
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v1
        with:
          files: docker/desktop/dist/**
```

### 11.7 README Badge + Download Link

```markdown
## Try on Desktop

No installation required. Download, unzip, run.

[![Download Desktop App](https://img.shields.io/badge/Desktop-Download-blue)](https://github.com/your-org/your-app/releases/latest)

**macOS (Apple Silicon):** [Download](https://github.com/your-org/your-app/releases/latest/download/yourapp-macos-arm64.zip)
**macOS (Intel):** [Download](https://github.com/your-org/your-app/releases/latest/download/yourapp-macos-x86_64.zip)
**Linux:** [Download](https://github.com/your-org/your-app/releases/latest/download/yourapp-linux-x86_64.tar.gz)

1. Download and unzip
2. Run `./yourapp-sqlite`
3. Browser opens at http://127.0.0.1:8765
4. Login: admin / admin
```

---

## 12. App Lifecycle Management — Install, Update, Uninstall, Migrate

### 12.1 Install New App

**In development (bench present):**

```bash
frappe-desktop app install hrms --site mysite
# or equivalently:
bench get-app hrms
bench --site mysite install-app hrms
bench --site mysite migrate
```

**In the binary/desktop app (no bench):**

Option A — Rebuild: Download app source, rebuild binary, restart.
Option B — Plugin system (future): A "Frappe Desktop Plugin" spec where apps are loaded from a separate directory at runtime without rebuilding. Requires the binary to have a plugin loader that can discover and import app modules at startup.

### 12.2 Uninstall App

```bash
frappe-desktop app uninstall hrms --site mysite
```

What it does:
1. `bench --site mysite uninstall-app hrms` — removes app's DocTypes and data
2. `pip uninstall hrms`
3. Remove `apps/hrms/`
4. Rebuild binary if in binary mode

**Data safety:** Uninstall creates a pre-uninstall backup first.

### 12.3 Update Apps

```bash
frappe-desktop app update                     # all apps
frappe-desktop app update frappe erpnext      # specific apps
frappe-desktop app update --check-only        # report available updates without applying
```

Update flow:
1. **Backup first.** `frappe-desktop backup --tag pre-update`
2. Stop server (or drain in-flight requests if multi-process)
3. `git pull origin <branch>` for each app
4. `pip install -e apps/<app>` (requirements may have changed)
5. `bench --site <site> migrate` (schema changes)
6. Rebuild binary if in binary mode
7. Restart server
8. Run smoke test (`/api/method/frappe.ping` + login)
9. If smoke fails: restore from pre-update backup, rollback `git`

### 12.4 Rebuild Binary

```bash
frappe-desktop build --site mysite
```

When is a rebuild needed?
- After installing or uninstalling an app (new Python modules added/removed)
- After updating an app that added new templates or fixtures
- After changes to `desktop_runtime/runner/`
- After Frappe core version bump

When is a rebuild **not** needed?
- After `migrate` (schema changes are in SQLite, not the binary)
- After updating CSS/JS assets only (assets are in `sites/assets/`, not frozen into the binary)
- After configuration changes to `site_config.json`

### 12.5 Migration Strategy

**Schema migrations** (`bench migrate`) are safe to run on a live SQLite site:
- DDL is transactional in SQLite (fix 1.3) — if migrate fails mid-way, it rolls back
- `PRAGMA integrity_check` runs after each table rebuild
- Pre-migration backup ensures rollback path

**Major version migrations** (e.g., Frappe v16 → v17):
1. Export all data: `bench --site <site> export-fixtures` + `bench export-csv`
2. Create fresh site on new version
3. Import data
4. Verify

**The known blocker (GAP):** `ImplicitCommitError` on `ALTER TABLE` — adding/dropping columns on existing tables fails. This is the top remaining gap. Fix: detect the `ImplicitCommitError` condition in `SQLiteDatabase` and route through the full table-rebuild path (which is already implemented and tested) instead of raising.

---

## 13. Site Management — Add, Remove, Clone, Export

### 13.1 Multiple Sites

SQLite fully supports multiple sites in the same bench. Each site is an independent `.db` file:

```
sites/
  site1.local/
    db/site1-local.db
    site_config.json
  site2.local/
    db/site2-local.db
    site_config.json
```

**In the desktop binary:** The seed site pattern supports multi-site. On first launch, seed all configured sites. The runner can accept `--site <name>` to select which site to serve, or serve all sites under different ports.

### 13.2 `frappe-desktop site new`

```bash
frappe-desktop site new mysite \
  --apps frappe,erpnext \
  --admin-password secret \
  --db-type sqlite
```

Creates site, installs apps, migrates, adds to seed bundle.

### 13.3 `frappe-desktop site clone`

```bash
frappe-desktop site clone production staging
```

1. `PRAGMA wal_checkpoint(FULL)` on source — flush WAL into main DB
2. `cp sites/production/db/*.db sites/staging/db/*.db`
3. Copy `private/files/` and `public/files/`
4. Update `site_config.json` (site name, any staging-specific config)
5. Run `bench --site staging migrate` to handle any pending schema changes

**Safe for offline copy while server is stopped.** For online (server running) clones: SQLite WAL guarantees that a file-level copy of the main `.db` file (while WAL exists) produces a consistent snapshot — but must checkpoint WAL first.

### 13.4 `frappe-desktop site export`

```bash
frappe-desktop site export mysite --out mysite-2026-06-07.tar.gz
```

Contents:
```
mysite-backup/
  db/mysite.db            ← checkpointed SQLite file
  site_config.json        ← stripped of secrets (optional)
  private/files/          ← uploaded files
  public/files/           ← public uploaded files
```

### 13.5 `frappe-desktop site import`

```bash
frappe-desktop site import mysite-2026-06-07.tar.gz --as restored-site
```

1. Extract tar.gz
2. Copy `.db` file to `sites/<name>/db/`
3. Copy config and files
4. Run `bench --site <name> migrate`
5. Verify with `PRAGMA integrity_check`

### 13.6 Multi-Site Desktop App

For a desktop app serving multiple sites (e.g., a consulting firm with multiple client deployments on one machine):

```bash
frappe-desktop run --all-sites     # each site on its own port
frappe-desktop run --site mysite   # single site
```

The runner auto-assigns ports from a range (e.g., 8765–8865) and opens a site-picker page at `http://127.0.0.1:8764` listing available sites with "Open" links.

---

## 14. Further Development Roadmap

### 14.1 P0 — Blockers (must fix before declaring stable)

**GAP: Schema alteration (`ALTER TABLE`)**

The biggest open gap. `ImplicitCommitError` blocks adding or dropping columns on existing tables. This means Customize Form field additions fail.

Fix strategy:
1. Catch `ImplicitCommitError` in `frappe/database/sqlite/schema.py`
2. Route to the existing full table-rebuild path (already implemented in `database.py`)
3. The rebuild path already handles PK, DEFAULT, CHECK, indexes, triggers

**GAP: Money/DECIMAL storage**

SQLite has no `DECIMAL` type. Currency fields land as `REAL` (IEEE-754). Decision needed:
- Option A: `TEXT` + Python `Decimal` — safe, slow for aggregates
- Option B: integer minor units — fast, requires UI/schema changes
- Option C: explicit limitation, block SQLite for financial apps

**Unresolved: `incrby` does not invalidate `frappe.local.cache`**

`LocalCache.incrby` increments the Redis-level value but does not invalidate `frappe.local.cache` (the in-process request cache). Same-request reads of an incremented value may see stale data.

Fix: after `incrby`, delete the corresponding key from `frappe.local.cache`.

### 14.2 P1 — Frappe Core Beta

- Full session round-trip: login, reload, session expiry, logout
- Permission-aware `get_list` for non-Administrator users
- Full schema alteration (depends on GAP fix above)
- Standard reports running on SQLite
- Webhook execution in sync mode
- Data import (small CSV)
- Browser automated smoke test (Playwright/Cypress)

### 14.3 P2 — App Compatibility

- ERPNext install + basic workflow (Sales Invoice, Customer, Item)
- HRMS install + basic workflow
- Custom app creation + custom DocType
- Report compatibility matrix

### 14.4 P3 — Polish and Hardening

- `estimate_count` using `MAX(rowid)` instead of `COUNT(*)` for large tables
- `is_deadlocked` → `return False` / `is_timedout` → match `"database is locked"` explicitly (currently both match the same string)
- `query_rewrite_cache` for repeated `%(name)s` → `:name` translations
- Persistent WAL+RO connection pool (separate read-only connection that never blocks writes)
- `STRICT` tables for new installs (SQLite 3.37+) — type enforcement at DB level
- Windows packaging (after macOS is proven)
- Linux AppImage (for portable Linux distribution)
- Auto-update with `tauri-plugin-updater`
- Code signing + notarization (macOS Gatekeeper compliance)

### 14.5 Phase 4 — Tauri Native App (NEXT IMMEDIATE ACTION)

1. `npm create tauri-app@latest` → `desktop_shell/`
2. Copy Phase 2 binary as Tauri sidecar
3. Wire sidecar launch in `main.ts`
4. Build `.app` and `.dmg`
5. End-to-end acceptance: native window, login, CRUD, persist, restart

### 14.6 `frappe-desktop` CLI Package (New Repo)

Create a standalone `frappe-desktop` Python package on PyPI:
- `pip install frappe-desktop`
- Works with any Frappe bench
- Auto-detects bench root
- Generates PyInstaller spec from app list
- Manages seed sites, build scripts, and update flows

---

## 15. Brainstorm — New Ideas

### 15.1 "One-Click Demo" Mode

When a user first opens the desktop app, instead of an empty site they get a **pre-loaded demo** with sample data (sample customers, items, invoices, projects). This is already supported by the seed site mechanism — just bundle a seed site with demo fixtures.

Implementation:
- `frappe-desktop build --with-demo-data` bundles a demo-data seed
- Demo data is generated by a script that runs `frappe.get_doc(...).insert()` for each fixture
- Demo can be reset: "Reset to Demo Data" button clears the SQLite file and re-copies the seed

### 15.2 Plugin System for Hot-Loading Apps

Instead of rebuilding the binary for every app change, implement a **plugin loader** that discovers apps from a `~/.frappe-desktop/apps/` directory at startup:

```python
import importlib, sys
from pathlib import Path

plugin_dir = Path.home() / ".frappe-desktop" / "apps"
for app_dir in plugin_dir.iterdir():
    sys.path.insert(0, str(app_dir))
    importlib.import_module(app_dir.name)
```

This allows:
- Installing apps without rebuilding the binary
- Updating apps without rebuilding
- Third-party apps distributed as zip files

Limitation: only works for pure-Python apps. Apps with compiled extensions still need a rebuild.

### 15.3 SQLite-Backed Scheduler (Replace Pause)

Currently `pause_scheduler=1` disables the scheduler entirely. A better approach for desktop use:

**SQLite-based job queue:** Replace the Redis RQ queue with a `tabScheduledJob` SQLite table. The scheduler runs in a background thread (not a separate process) and polls the table.

```python
# In scheduler.py, local mode:
def run_pending_jobs():
    jobs = frappe.get_all("Scheduled Job Type",
        filters={"stopped": 0, "next_execution": ["<=", now()]},
        fields=["name", "method"])
    for job in jobs:
        frappe.enqueue(job.method)  # executes sync in local mode
        update_next_execution(job.name)
```

This gives the desktop app scheduled tasks (send emails, sync data, generate reports) without Redis.

### 15.4 Local WebSocket (Replace Noop Realtime)

Replace `realtime_backend=noop` with a real local WebSocket server (no Redis pubsub):

```python
# Simple asyncio WebSocket server
import asyncio, websockets, json
from threading import Thread

_subscribers = {}   # event_name -> set of websocket connections

async def handler(ws):
    async for message in ws:
        data = json.loads(message)
        _subscribers.setdefault(data["event"], set()).add(ws)

def publish_local(event, message):
    for ws in _subscribers.get(event, set()):
        asyncio.run_coroutine_threadsafe(ws.send(json.dumps(message)), _loop)
```

Wire `frappe.publish_realtime` to call `publish_local`. This restores progress bars, live list updates, and form refresh — the features that make Frappe's UI feel responsive.

### 15.5 Offline-First Sync (Multi-Device)

For power users who want data on multiple machines without a server:

1. Each device has its own SQLite file
2. Changes are tracked in a `tabChangeLog` table (doctype, name, field, old, new, timestamp, device_id)
3. Sync happens via:
   - Direct device-to-device (LAN sync using mDNS discovery)
   - Cloud relay (user-provided S3/Cloudflare R2 bucket, encrypted)
   - Manual export/import of change log

This is a major feature, but the single-file SQLite foundation makes it more feasible than with MariaDB.

### 15.6 Embedded Admin Panel

A separate admin tab in the desktop app (not part of Frappe Desk) for managing the desktop installation:

```
http://127.0.0.1:8765/__admin/
  Sites       → list, create, clone, backup, delete
  Apps        → installed apps, update, uninstall
  Settings    → data directory, port, auto-start on login
  Logs        → tail app logs
  Diagnostics → SQLite PRAGMA info, WAL size, DB integrity
  Backup      → manual backup + restore
```

This replaces the need for `bench` commands for non-developers.

### 15.7 App Marketplace Integration

A curated list of Frappe-compatible desktop apps, browseable from the admin panel:

```
http://127.0.0.1:8765/__admin/marketplace
  Featured: ERPNext, HRMS, CRM, Helpdesk
  Community: ...
  [Install] button → downloads and installs the app
```

The marketplace is a static JSON file hosted on GitHub Pages:
```json
{
  "apps": [
    {
      "name": "erpnext",
      "display_name": "ERPNext",
      "version": "15.0.0",
      "repo": "https://github.com/frappe/erpnext",
      "branch": "version-16",
      "description": "...",
      "desktop_tested": true,
      "size_mb": 45
    }
  ]
}
```

### 15.8 Docker Compose Profile for Each App

Every Frappe app repo gets a `docker/` directory with profiles:

```yaml
# docker/docker-compose.yml
services:
  # Standard development (MariaDB + Redis)
  frappe:
    profiles: [dev]
    image: frappe/bench
    ...

  # Desktop/SQLite build
  desktop-builder:
    profiles: [desktop]
    build: ./desktop/
    ...

  # CI test (SQLite, no external services)
  test:
    profiles: [ci]
    image: frappe/bench
    command: bench run-tests --sqlite
    ...
```

Usage:
```bash
docker compose --profile dev up         # normal dev
docker compose --profile desktop run builder  # build binary
docker compose --profile ci run test    # run SQLite tests in CI
```

### 15.9 `frappe test --sqlite` Flag

Add a `--sqlite` flag to `bench run-tests` that:
1. Creates a temporary SQLite site
2. Sets all four local-mode config keys
3. Runs the test suite with MariaDB/Redis stopped
4. Tears down the temporary site

This makes SQLite CI testing a one-command operation for any Frappe app.

### 15.10 Incremental Binary Updates (Delta Patching)

Instead of downloading a full 32 MB binary for every update, distribute delta patches:
- `bsdiff` to compute `old_binary → new_binary` patch
- `bspatch` on the client to apply it
- Patches can be ~1 MB for small app updates vs 32 MB for full binary

The Tauri auto-updater already supports this via `tauri-plugin-updater` with ZSTD-compressed bundles.

### 15.11 Read Replica SQLite Connection

For read-heavy workloads, open a second `READONLY` SQLite connection:

```python
self.read_conn = sqlite3.connect(db_path,
    check_same_thread=False,
    uri=True,
    database=f"file:{db_path}?mode=ro")
```

Route all `SELECT` queries (identified by `frappe.db.sql(..., as_read=True)` or query builder `SELECT` statements) through the read connection. Write transactions (`INSERT`, `UPDATE`, `DELETE`, `BEGIN IMMEDIATE`) go through the write connection. Readers never block on write transactions in WAL mode.

### 15.12 Frappe Desktop as a Frappe App

Package `frappe-desktop` as a Frappe app that:
- Adds a "Desktop Build" button to the Frappe UI
- Lets admins configure build settings (product name, included apps, platforms)
- Triggers a CI build via GitHub Actions webhook
- Shows build status and download links
- One-click "Build Desktop App" from within Frappe itself

---

## Summary: The Big Picture

What we built in Phase 1 is the **foundation layer**. The dependency graph looks like:

```
Phase 1 (DONE)
  SQLite core DB + schema + fixes
  In-process cache (LocalCache)
  Sync queue (background_jobs)
  Noop realtime
  36-test suite
      ↓
Phase 2 (IN PROGRESS)
  Full query/filter/join coverage
  Session + permissions
  Background features (scheduler, webhooks, data import)
  Search (FTS5)
      ↓
Phase 3 (DONE — binary smoke test)
  PyInstaller build
  Seed site bundling
  Smoke test pass
      ↓
Phase 4 (NEXT)
  Tauri native window
  Sidecar lifecycle
  .app + .dmg
      ↓
Phase 5 (FUTURE)
  frappe-desktop CLI tool
  "Try on Desktop" Docker pattern
  App marketplace
  Auto-updater
  Multi-site admin panel
  Offline sync
```

The single most important next action is **fixing the schema alteration blocker** (route `ImplicitCommitError` through the table-rebuild path). That unblocks Customize Form field additions, which is the most common reason a developer would touch the schema on a running site.

The second most important action is **Phase 4 (Tauri)** — closing the last gap between "binary that works" and "native desktop app that any user can install".

Everything else (frappe-desktop CLI, app marketplace, offline sync, plugin system) flows naturally once the native app is real and in users' hands.
