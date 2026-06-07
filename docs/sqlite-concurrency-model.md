# SQLite Concurrency Model

**Branch:** `poc/sqlite-only-runtime-plan`
**Status:** Documented decision — governs `BEGIN IMMEDIATE`, `for_update`, `estimate_count` (2.5), and retry semantics (4.3).

---

## The model in one sentence

SQLite under WAL gives **many concurrent readers + exactly one writer at a time**; the safe deployment envelope for a Frappe SQLite site is **1 write-worker process** (or a tightly bounded small pool with `BEGIN IMMEDIATE` + retry).

---

## Write locking

### How it works

SQLite WAL uses a file-level write lock.  Only one connection can hold the write lock at a time.  Under WAL, readers never block writers and writers never block readers — but two concurrent writers contend for the single write lock.

### What `BEGIN IMMEDIATE` does (fix 4.1)

`SQLiteDatabase.begin()` issues `BEGIN IMMEDIATE` for all non-read-only transactions.  This acquires the write lock **up-front**, at transaction start, rather than lazily on the first write statement.

**Why this matters:**
- With `BEGIN` (deferred), two workers can both `BEGIN`, both read, then both attempt their first write — only one succeeds; the other gets `SQLITE_BUSY` ("database is locked") **mid-transaction**, after it has already done work.
- With `BEGIN IMMEDIATE`, the loser fails **immediately** at the `BEGIN` statement (before any work is done), waits `busy_timeout` ms, and retries cleanly.

### Timeout chain

| Layer | Value | Purpose |
|-------|-------|---------|
| `PRAGMA busy_timeout` | 5 000 ms | How long SQLite retries the write-lock before raising `OperationalError: database is locked` |
| Python `sqlite3.connect(timeout=)` | 6 s | Outer OS-level timeout; slightly higher than busy_timeout so SQLite always fires first |

These are unified in `SQLiteDatabase._BUSY_TIMEOUT_MS` and `_CONNECT_TIMEOUT_S`.

---

## `for_update` is a no-op by design (finding 1.4)

`frappe/model/document.py` skips `FOR UPDATE` on SQLite (`db_type != "sqlite"`).

**Why this is correct and safe:**
- `FOR UPDATE` in MariaDB/Postgres locks a row so no other transaction can write it between your `SELECT` and your subsequent `UPDATE`.
- On SQLite, `BEGIN IMMEDIATE` achieves the same guarantee at a coarser granularity: once you hold the write lock, **no other writer can enter a transaction at all** until you commit or rollback.  There is no window for another writer to modify your row.
- This is **more exclusive** than MariaDB's row-level `FOR UPDATE`, not less — it just applies to the whole database rather than a single row.

**Documented decision:** `for_update` is a no-op on SQLite because `BEGIN IMMEDIATE` makes it redundant.  This is safe as long as the single-writer envelope below is respected.

---

## Safe deployment envelope

| Deployment type | Safe write workers | Notes |
|----------------|-------------------|-------|
| Single-user embedded (binary app, local dev) | 1 | No contention possible |
| Small team / internal tool | 1–3 gunicorn workers | `BEGIN IMMEDIATE` + 5 s `busy_timeout` absorbs bursts; p99 write latency stays low |
| Medium load (< ~50 concurrent users) | 2–4 workers | Monitor WAL size; set `wal_autocheckpoint = 1000` (done) |
| High write throughput / financial transactions | **1 worker + queue** | Route writes through a single worker via `enqueue`; use Redis queue replacement (the SQLite queue backend in this POC) |
| Multi-region / multi-host | ❌ Not supported | SQLite is a single-file database; cross-host writes require a server DB |

**Rule of thumb:** if your p95 write request time × concurrent write workers > 4 s, you will see `database is locked` errors under load.  Add a write queue or move to MariaDB.

---

## `is_deadlocked` vs `is_timedout` (finding 4.3)

Both predicates currently match `"database is locked"` — they cannot be distinguished on SQLite.

**Why this is acceptable in the short term:**
- SQLite has **no true deadlock** under a single-writer model.  Two transactions cannot each hold a lock the other needs; the write lock is singular.
- Every `"database is locked"` error is therefore a **contention timeout**, not a deadlock.
- The correct retry semantics are: bounded exponential backoff (not "give up immediately" as for a deadlock).

**Recommended explicit policy (post-beta):**
```python
# In SQLiteExceptionUtil:
@staticmethod
def is_deadlocked(e): return False  # SQLite has no deadlocks
@staticmethod
def is_timedout(e): return "database is locked" in str(e)
```
This routes all lock contention to the retry path, not the error path.  Not implemented yet — tracked as finding 4.3 (post-beta).

---

## `estimate_count` (finding 2.5)

`estimate_count()` currently runs `SELECT COUNT(*)`, which walks the table or smallest index.  This is correct but expensive on large tables.

**Unblocked now:** the safe alternative is `SELECT MAX(rowid)` as a cheap upper-bound estimate.  This is valid because:
- SQLite `rowid` is monotonically assigned; gaps exist after deletes but MAX(rowid) ≥ actual row count.
- For list-view "total" counts an approximate upper bound is acceptable.

```python
def estimate_count(self, doctype: str):
    table = get_table_name(doctype)
    try:
        row = self.sql(f"SELECT MAX(rowid) FROM `{table}`")
        return cint(row[0][0]) if row and row[0][0] is not None else 0
    except sqlite3.OperationalError as e:
        if not self.is_table_missing(e):
            raise
    return 0
```

Tracked as finding 2.5 — implement as a follow-up to this doc.

---

## Summary of decisions made

| Finding | Decision |
|---------|----------|
| 4.1 | `BEGIN IMMEDIATE` for all write transactions — **implemented** |
| 4.2 | Single timeout constant — **implemented** |
| 1.4 | `for_update` is no-op by design; `BEGIN IMMEDIATE` makes writer exclusive — **documented** |
| 4.3 | All "database is locked" → retry (not deadlock); explicit separation post-beta |
| 2.5 | `MAX(rowid)` estimate unblocked; implement as follow-up |
