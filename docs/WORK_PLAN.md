# SQLite-First Fixes — Work Plan & Tracker

**Canonical branch:** `poc/sqlite-only-runtime-plan` (sqlite/fixes-phase1 merged ✅)
**Base:** `poc/sqlite-only-runtime-plan` (committed baseline: `433b191b78`)
**Repo:** `/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc`
**Docker bench:** `devcontainer-frappe-1` at `/Users/safwan/Code/docker/fdocker/.devcontainer`
**SQLite version in use:** 3.51.0

---

## Source of truth for agents

This file is updated after every fix. If you are a Kimi/Claude worker picking up a task:

1. Read this file first to understand context and which fixes are pending.
2. Read `docs/sqlite-first-design-review.md` for the full rationale behind each fix.
3. Work **only** in the files listed under your fix. Do not touch other files.
4. Do not commit — Claude (orchestrator) reviews and commits.
5. After each fix, update the Status column below with: ✅ done / ❌ failed / 🔄 partial + notes.

---

## Fix sequence and ownership

Fixes are ordered by priority: correctness blockers first, then perf, then knobs.
Each Kimi worker handles one fix at a time. Tests are run after each fix before proceeding.

| # | ID | Fix | Files | Status | Notes |
|---|----|-----|-------|--------|-------|
| 1 | 1.2 | ALTER TABLE: use native RENAME/DROP COLUMN; 12-step rebuild for type changes | `frappe/database/sqlite/schema.py`, `frappe/database/sqlite/database.py` | ✅ done | commit f2e64004 |
| 2 | 1.3 | Transactional DDL: remove auto-commit guard; let DDL be part of transaction | `frappe/database/sqlite/database.py` | ✅ done | commit e6434c0d |
| 3 | 4.1 | BEGIN IMMEDIATE for write transactions; unify timeout (fix 4.2 too) | `frappe/database/sqlite/database.py` | ✅ done | commit 7da6e300 |
| 4 | 2.2 | Dict-value named binding: %(name)s → :name, bind via sqlite3 native | `frappe/database/sqlite/database.py` | ✅ done | commit 7da6e300 |
| 5 | 2.4 | Remove Python CONCAT_WS shim (native in SQLite 3.44+) | `frappe/database/sqlite/database.py` | ✅ done | commit 7da6e300 |
| 6 | 3.1 | PRAGMA profile: add cache_size, mmap_size, temp_store; WAL once at creation | `frappe/database/sqlite/database.py`, `frappe/database/sqlite/setup_db.py` | ✅ done | commit bc9eebab |

---

## Fix details

### Fix 1 — ID 1.2: ALTER TABLE rebuilds

**Problem:** `schema.py::SQLiteTable.alter()` and `database.py::change_column_type()`/`rename_column()` do a full table rebuild from `PRAGMA table_info` which only carries name+type. This silently drops: secondary indexes, DEFAULT values, CHECK constraints, PRIMARY KEY/AUTOINCREMENT, triggers.

**Solution:**
- `rename_column()` → use `ALTER TABLE … RENAME COLUMN` (available since SQLite 3.25; we have 3.51)
- `drop_column()` / `alter()` for drops → use `ALTER TABLE … DROP COLUMN` (3.35+)
- For genuine type-change rebuilds: implement the official SQLite 12-step procedure:
  1. `PRAGMA foreign_keys=OFF`
  2. Begin transaction
  3. `SELECT sql FROM sqlite_master WHERE type IN ('table','index','trigger') AND tbl_name = ?` — save all schema
  4. Create `_new` table with updated column type
  5. Copy rows
  6. DROP original
  7. RENAME `_new` → original
  8. Re-create all saved indexes and triggers (not just the ones `alter()` was asked for)
  9. `PRAGMA foreign_key_check`
  10. Commit
  11. `PRAGMA foreign_keys=ON`

**Files:** `frappe/database/sqlite/schema.py`, `frappe/database/sqlite/database.py`
**Test:** Add/run `frappe/tests/test_sqlite_schema.py` — verify index survives rename, verify type-change rebuild preserves all indexes.

---

### Fix 2 — ID 1.3: Transactional DDL

**Problem:** `check_implicit_commit()` forces a commit before any DDL in the SQLite driver. `add_index`, `add_unique`, `sql_ddl` each call `self.commit()` around DDL. This breaks atomic migrations — a partial failure mid-migration can't roll back.

**Solution:**
- In `frappe/database/sqlite/database.py`: override `check_implicit_commit` to be a no-op (just `pass` or `return`) — SQLite DDL is fully transactional.
- Remove the `self.commit()` calls flanking DDL statements in the SQLite-specific path.
- Keep existing `self.commit()` calls in the MariaDB/Postgres paths untouched.

**Files:** `frappe/database/sqlite/database.py`
**Test:** Confirm a multi-step migration that fails at step N rolls the whole transaction back.

---

### Fix 3 — ID 4.1 + 4.2: BEGIN IMMEDIATE + unified timeout

**Problem:** `begin()` issues `BEGIN` (deferred). Two concurrent transactions can both start reading, then both try to upgrade to writer, and one gets `SQLITE_BUSY` mid-transaction. Also two timeout mechanisms: Python `timeout=15` and `PRAGMA busy_timeout=5000` with different values.

**Solution:**
- Change `begin()` to issue `BEGIN IMMEDIATE` for any non-read-only transaction. Read-only transactions can stay as `BEGIN` (or use `BEGIN DEFERRED`).
- Unify timeout: pick `busy_timeout` (PRAGMA, at connection level) as source of truth. Set Python `timeout` parameter to a compatible value or derive from the same constant.
- Add a comment documenting the single-writer model.

**Files:** `frappe/database/sqlite/database.py`
**Test:** Confirm `BEGIN IMMEDIATE` is issued; confirm timeout constant is consistent.

---

### Fix 4 — ID 2.2: Dict-value named binding

**Problem:** In `execute_query()`, when `values` is a dict, the code manually quotes strings and does `query = query % values` — interpolating values into SQL text. This (a) defeats prepared-statement cache, (b) is a SQL injection surface.

**Solution:**
- Detect `%(name)s` style placeholders when values is a dict.
- Replace `%(name)s` → `:name` using regex.
- Pass the dict directly to `cursor.execute(query, values)` — sqlite3's native named binding.
- Remove the manual quoting loop.

**Files:** `frappe/database/sqlite/database.py`
**Test:** Confirm dict-valued queries bind correctly; confirm a value with SQL chars doesn't break the query.

---

### Fix 5 — ID 2.4: Remove Python CONCAT_WS shim

**Problem:** `CONCAT_WS` is registered as a Python UDF via `conn.create_function`. Every invocation crosses the C↔Python boundary. On SQLite 3.44+, `concat_ws()` is a native built-in.

**Solution:**
- Remove the `create_function("CONCAT_WS", ...)` registration.
- Verify that any Frappe queries using `CONCAT_WS(...)` work against the native SQLite function (which has the same signature).
- Keep `regexp` and `regexp_replace` Python UDFs (still needed).

**Files:** `frappe/database/sqlite/database.py`
**Test:** Run a query with `CONCAT_WS` and confirm it returns correct results without the Python shim.

---

### Fix 6 — ID 3.1: PRAGMA performance profile

**Problem:** Only `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout` set. Missing: `cache_size`, `mmap_size`, `temp_store`, `wal_autocheckpoint`. Also WAL is re-asserted on every connection even though it persists in the DB header.

**Solution:**
- In `get_connection()`: add `PRAGMA cache_size = -32768` (32 MB), `PRAGMA mmap_size = 134217728` (128 MB), `PRAGMA temp_store = MEMORY`.
- Move `PRAGMA journal_mode = WAL` to `setup_db.py` (site creation), not per-connection.
- Set `PRAGMA wal_autocheckpoint = 1000` per connection (or document the policy).
- Add a `PRAGMA foreign_keys = OFF` with a comment that app-level integrity is used (fix 3.2 documented decision).
- Add inline comments explaining each pragma and the "server profile" vs "embedded profile" distinction.

**Files:** `frappe/database/sqlite/database.py`, `frappe/database/sqlite/setup_db.py`
**Test:** Confirm pragmas are set; confirm WAL mode is still active after a fresh connection.

---

## Testing approach

All tests run inside `devcontainer-frappe-1`.

```bash
# Enter container
docker exec -it devcontainer-frappe-1 bash

# Run SQLite-specific tests
cd /workspace/frappe
python -m pytest frappe/tests/test_sqlite_schema.py -v
python -m pytest frappe/tests/test_sqlite_only_runtime.py -v

# Or via bench
bench --site dev.localhost run-tests --app frappe --module frappe.tests.test_sqlite_schema
```

After all fixes, full regression:
```bash
bench --site dev.localhost run-tests --app frappe
```

---

## Merge plan

✅ **DONE** — sqlite/fixes-phase1 merged to poc/sqlite-only-runtime-plan (2026-06-07).

---

## Explicitly deferred (post-beta)

These are **not gaps** — they are named, reasoned deferrals.  Pick up after the first real-world pilot.

| ID | Finding | Why deferred |
|----|---------|-------------|
| 2.1 | 4–6 string/regex rewrites per query | Memoizing `modify_query` requires thread-safe LRU on potentially non-hashable query objects; perf win is real but refactor risk is medium. Post-beta. |
| 2.3 | Connection close/reopen on `read_only` toggle | Persistent RW+RO connection pool is a bigger refactor; requires connection state tracking across Frappe's `connect()`/`close()` lifecycle. Post-beta. |
| 3.3 | STRICT tables unused | Optional opt-in for new sites; no urgency until pilot data shows affinity-coercion bugs in practice. Post-beta. |
| 2.5 | `estimate_count` = full `COUNT(*)` | Safe fix (`MAX(rowid)`) is now unblocked by the concurrency-model doc. Implement as a standalone 1-line follow-up. |
| 4.3 | `is_deadlocked` == `is_timedout` | Separate to `is_deadlocked = False` / `is_timedout = "locked"`. Explicit policy documented in `sqlite-concurrency-model.md`. Small change, post-beta. |

---

## DECISION REQUIRED — Finding 1.1: Money stored as REAL

**Status:** Unresolved. Blocks any financial rollout (invoicing, VAT, multi-currency).

### The problem

`setup_type_map()` maps `Currency`, `Float`, `Percent`, `Rating`, `Duration` → SQLite `REAL` (IEEE-754 binary float).  On MariaDB these are `DECIMAL(21,9)` — exact base-10.  `REAL` accumulates rounding error: `0.1 + 0.2 ≠ 0.3`, tax splits, running totals silently corrupt.

### Options

| Option | Pro | Con | Scope impact |
|--------|-----|-----|-------------|
| **A. Integer minor units** (store fils/cents, scale in app) | Exact arithmetic, no library needed | Every read/write must scale; `flt()` / `precision` logic needs a SQLite branch | High — touches how Currency round-trips |
| **B. TEXT + `decimal.Decimal`** | Exact, readable, no schema change | Every arithmetic op needs explicit `Decimal`; Frappe's `flt()` already wraps precision so hooking it is feasible | Medium — hook in `flt()` and `db.escape()` for SQLite |
| **C. Keep REAL, document limitation** | Zero code change | Silent data corruption in any finance app; unacceptable for production financial data | Acceptable only for non-financial sites |

### Recommended default

**Option B (TEXT + Decimal) scoped to SQLite-only**, with `flt()` routing through `Decimal` for the SQLite branch.  This is the least invasive change with no schema migration required on existing SQLite sites.  Explicitly mark SQLite as "no multi-currency sub-fil precision guarantee" for the rare edge case where that matters.

### Decision needed from

Product/architecture owner — this is not a coding decision.  Once decided, implementation is 1–2 days.

**Do not implement until the decision is recorded in `docs/DECISIONS.md`.**

---

## Change log

| Date | Action | Agent |
|------|--------|-------|
| 2026-06-07 | Branch created: sqlite/fixes-phase1. Baseline committed (433b191b78). WORK_PLAN.md written. | Claude |
| 2026-06-07 | All 6 fixes implemented. 36/36 tests pass (sqliteonly.localhost). Branch ready to merge. | Claude |
| 2026-06-07 | sqlite/fixes-phase1 merged to poc/sqlite-only-runtime-plan. 36/36 tests pass with MariaDB+Redis stopped. One canonical tree. | Claude |
| 2026-06-07 | 1.2b: change_column_type rewritten to use sqlite_master CREATE TABLE sql — PK/AUTOINCREMENT/DEFAULT/CHECK/triggers all preserved. 36/36 tests pass. | Claude |
| 2026-06-07 | 1.4: for_update doc note added to document.py (both sites). Concurrency model doc written (sqlite-concurrency-model.md). 2.5 and 4.3 unblocked. | Claude |
| 2026-06-07 | 2.1, 2.3, 3.3 explicitly deferred post-beta. 1.1 money decision memo added below. | Claude |
