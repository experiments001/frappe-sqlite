# SQLite-First Design & Performance Review

Date: 2026-06-07
Status: **Documentation only — no code changed.** Findings for a future "SQLite as a serious stack for critical rollouts" decision.
Scope reviewed: `frappe/database/sqlite/{database.py,schema.py,setup_db.py}`, `frappe/database/database.py` (base), `frappe/model/document.py`.
Environment: bundled SQLite **3.51.0** (very recent — this materially changes what's possible; see below).

---

## How to read this

The current SQLite support is a **port of the MariaDB driver**: it keeps MariaDB's mental model (auto-committing DDL, row-level pessimistic locks, `DECIMAL` money, server-side row-count estimates, native regex) and emulates or stubs each one for SQLite. That is the correct way to get a POC passing tests fast, and it works.

A **SQLite-first** lens asks a different question: given SQLite's actual strengths (transactional DDL, a single-file store, WAL, fast `?`-bound prepared statements) and its actual weaknesses (no `DECIMAL`, single writer, limited `ALTER TABLE`, Python-bridged UDFs), how should the layer behave so it is *fast and safe by design* rather than *MariaDB-shaped and patched*?

Everything below is non-breaking: each item can be adopted behind the `db_type == "sqlite"` branch without touching MariaDB/Postgres behavior or rewriting the framework. Items are tagged:

- **CORRECTNESS** — can lose or corrupt data; blocks critical rollouts.
- **PERF** — wastes CPU/IO on the hot path; safe but slower than it needs to be.
- **KNOB** — a SQLite tuning lever that is currently absent or undocumented.

---

## Tier 1 — Correctness landmines (block "critical rollout")

### 1.1 Money stored as `REAL` (floating point) — CORRECTNESS
`frappe/database/sqlite/database.py` `setup_type_map()` maps `Currency`, `Float`, `Percent`, `Rating`, `Duration` → `REAL`. On MariaDB, `Currency` is `DECIMAL(21,9)` — exact base-10 arithmetic. `REAL` is IEEE-754 binary float, so values like `0.1 + 0.2`, tax splits, and running totals accumulate rounding error. For any finance/VAT/invoicing rollout this is the single biggest blocker — it is a *silent* data-integrity defect, not a crash.

SQLite has no native `DECIMAL` type. SQLite-first options, in order of safety:
- Store monetary amounts as **integer minor units** (cents/fils) and scale in the app layer.
- Store as **`TEXT`** and do all math with Python `decimal.Decimal` (Frappe already uses `flt`/precision logic that could route through Decimal for SQLite).
- Use the `decimal` extension or a `NUMERIC`-affinity column *with* explicit rounding at every write — fragile, not recommended for critical money.

This deserves an explicit, documented decision before any financial app is considered "supported."

### 1.2 `ALTER TABLE` rebuilds silently drop indexes, constraints, defaults — CORRECTNESS
`schema.py::SQLiteTable.alter()` and `database.py::change_column_type()` / `rename_column()` implement column changes the pre-3.25 way: create `tab..._new`, copy rows, `DROP` original, rename. The rebuilt table is reconstructed from `PRAGMA table_info`, which only carries **name + type** (and sometimes `notnull`). That means a rebuild can lose:
- the `name ... PRIMARY KEY` / `AUTOINCREMENT` designation,
- column `DEFAULT`s,
- `CHECK` constraints,
- **all secondary indexes** (in `change_column_type`/`rename_column` nothing recreates them; `alter()` only recreates the specific add_index/add_unique it was asked for),
- triggers and any FTS shadow wiring.

Symptoms in production: a "rename a field" migration quietly drops the index on a hot column → a list view that was instant becomes a full table scan; or a lost `NOT NULL`/default lets bad rows in. Because SQLite is now **3.51**, most rebuilds are unnecessary:
- `ALTER TABLE … RENAME COLUMN` (3.25+) — use for `rename_column`.
- `ALTER TABLE … DROP COLUMN` (3.35+) — use for drops.
- `ALTER TABLE … ADD COLUMN` — already used.
- For genuine type changes, follow SQLite's official **12-step rebuild** (save schema of indexes/triggers, `PRAGMA foreign_keys=OFF`, rebuild, recreate *all* indexes/triggers, `PRAGMA foreign_key_check`) inside one transaction — not the column-only copy used today.

### 1.3 Transactional DDL is thrown away to emulate MariaDB — CORRECTNESS + PERF
`check_implicit_commit()` (overridden in the SQLite driver) carries forward MariaDB's rule that DDL auto-commits, and `add_index`, `add_unique`, and `sql_ddl()` each call `self.commit()` around DDL. But **SQLite DDL is fully transactional** — `CREATE`/`ALTER`/`DROP`/`CREATE INDEX` can run inside `BEGIN … COMMIT` and roll back cleanly. The MariaDB-era guard does two harmful things on SQLite:
1. It forces extra commits mid-migration (each commit is a WAL/fsync boundary → slower migrates and, worse, a *partially applied* schema if a later step fails).
2. It discards SQLite's best operational feature: a `migrate` that either fully applies or fully rolls back.

SQLite-first: wrap a DocType sync / migration unit in a single transaction and let it roll back on error. This is both safer and faster, and is the opposite of how the port currently behaves. (Note: the recent fix that turned `check_implicit_commit` from "raise" to "commit-first" papered over the symptom; the design-level answer is "don't auto-commit DDL at all on SQLite.")

### 1.4 `SELECT … FOR UPDATE` is silently a no-op — CORRECTNESS
`frappe/model/document.py:254` and `:337`: `if self.flags.for_update and frappe.db.db_type != "sqlite": for_update = "FOR UPDATE"`. On SQLite the clause is dropped to an empty string with no warning. Pessimistic row locking simply doesn't happen. Under concurrent submit/cancel/update this can break document invariants that the MariaDB path protects. This is acceptable *if* the concurrency model is explicitly single-writer (see Tier 4), but right now it is an undocumented silent divergence. SQLite-first answer: take the write lock for the whole transaction with `BEGIN IMMEDIATE` (see 4.1), and document that `for_update` is a no-op because the writer is already exclusive.

---

## Tier 2 — Per-query performance taxes (hot path)

Frappe issues *many* small queries per request, so anything per-statement multiplies.

### 2.1 Multiple string/regex rewrites on every single query — PERF
Each `db.sql()` call on SQLite passes through, in order:
1. base `database.py`: `IFNULL_PATTERN.sub("coalesce(", query)` + `get_query_type()` parse;
2. SQLite `sql()` override → `modify_query()`: `str(query)`, `.replace("\`", '"')`, `replace_locate_with_instr()` (regex search, maybe sub), and a `from tab…` regex search (maybe sub);
3. `execute_query()`: `query.replace("%s", "?")`, plus — for dict values — per-key quoting and a `query % values` interpolation.

That is **4–6 full-string scans per statement**, none memoized. On a Desk page that fires hundreds of queries this is real CPU. SQLite-first reduces it by (a) caching the transformed form keyed on the original query object identity, and/or (b) authoring the framework's SQLite queries already in SQLite dialect (double-quoted idents, `?`/named params, `instr`) so the rewrite is a cheap no-op or skipped entirely.

### 2.2 Dict-value path bypasses prepared statements (and is an injection vector) — CORRECTNESS + PERF
`execute_query()`: when `values` is a dict it manually quotes strings and does `query = query % values` — i.e. it **interpolates values into SQL text** instead of binding them. This (a) defeats SQLite's prepared-statement cache because every call is a textually different query, and (b) is a classic SQL-injection surface if any value reaches it unescaped. SQLite-first: convert `%(name)s` → named `:name` placeholders and bind them; never string-format values into the query.

### 2.3 Connection churn when `read_only` toggles — PERF
`begin()` **closes and reopens** the connection every time `frappe.flags.read_only` flips. Each reopen re-runs the PRAGMAs, re-registers the Python UDFs (`regexp`, `regexp_replace`, `CONCAT_WS`), and throws away the connection's page cache **and** statement cache. Frappe flips read-only frequently (e.g. GET request handling). SQLite-first: hold a persistent RW connection and a persistent RO connection (or a single connection plus `PRAGMA query_only=ON/OFF`) and switch the cursor, instead of `close()`/reconnect.

### 2.4 SQL functions implemented in Python on the row path — PERF
`regexp`, `regexp_replace`, and `CONCAT_WS` are registered as Python callbacks (`conn.create_function`). Every invocation crosses the C↔Python boundary per row. A `REGEXP` filter or a `CONCAT_WS` projection over a large result set is dramatically slower than MariaDB's native C implementations. On SQLite 3.51 specifically:
- `concat_ws()` / `concat()` are **native since 3.44** — the Python `CONCAT_WS` shim is no longer needed.
- `REGEXP` in a `WHERE` can't use an index regardless; SQLite-first pushes text matching to `LIKE`/`GLOB` (sargable with the right collation) or to **FTS5**, which already exists for global search.

### 2.5 `estimate_count()` does a full `COUNT(*)` — PERF
MariaDB's `estimate_count` reads an approximate row count from `information_schema` in O(1). The SQLite version runs `SELECT COUNT(*)`, which walks the table (or smallest index). List-view "total" and any code calling `estimate_count` on a large table pays a full scan. SQLite-first: use `MAX(rowid)` as a cheap upper-bound estimate, or maintain a lightweight per-table counter, or cache the count with short TTL — reserving exact `COUNT(*)` for when it's actually requested.

### 2.6 `PARSE_DECLTYPES` converters run per value — PERF
`create_connection()` sets `detect_types=sqlite3.PARSE_DECLTYPES` and registers Python converters for `timestamp`/`date`/`time`. Since nearly every Frappe row has `creation` and `modified` datetimes, most reads invoke a Python converter **per dated column per row**. Worth measuring whether deferring conversion to the app layer (read ISO text, convert lazily where actually needed) is cheaper at scale.

### 2.7 PRAGMAs re-issued on every connection — PERF (minor)
`get_connection()` sets `journal_mode=WAL` on every connect, but WAL is **persisted in the database header** — it only needs setting once at site creation. `synchronous` and `busy_timeout` are per-connection and correctly set each time. Minor, but re-asserting WAL per connection can trigger avoidable checkpoint/IO work.

---

## Tier 3 — Missing SQLite-first knobs (currently absent)

These are pure additions; none change MariaDB behavior.

### 3.1 No PRAGMA performance profile beyond the basics — KNOB
Today: `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`. Good start, but the real SQLite levers are undocumented and unset:
- `cache_size` (negative = KiB; default 2MB is small for a server),
- `mmap_size` (memory-map the DB for read-heavy workloads),
- `temp_store=MEMORY` (sorts/temp B-trees in RAM),
- `wal_autocheckpoint` / explicit checkpoint policy (WAL grows unbounded under sustained writes without a checkpoint strategy — an operational risk for long-running sites),
- `foreign_keys` policy (see 3.2).

A documented "SQLite server profile" vs "SQLite embedded/CLI profile" would make tuning intentional.

### 3.2 Foreign-key enforcement is undecided — KNOB / CORRECTNESS
SQLite defaults `foreign_keys=OFF`. Frappe relies on app-level integrity, so this may be fine — but it must be a *documented* decision, because the table-rebuild path (1.2) toggling FKs implicitly can mask reference breakage. Decide and document: enforced, or explicitly off-by-design.

### 3.3 STRICT tables not considered — KNOB / CORRECTNESS
SQLite 3.37+ supports `STRICT` tables, which reject type-mismatched writes (no silent affinity coercion). For a "serious stack" this closes a class of "string written into an integer column" bugs that MariaDB would have rejected. Worth evaluating as an opt-in for new SQLite sites.

---

## Tier 4 — Concurrency model (the decisive factor for critical rollouts)

### 4.1 Single-writer reality vs. multi-worker deployment — CORRECTNESS
WAL gives **many concurrent readers + exactly one writer**. A typical Frappe deployment runs multiple gunicorn workers (and a scheduler), so several processes contend for the one write lock. The current code relies on `busy_timeout=5000` to absorb contention, but uses `BEGIN` (deferred) — the write lock is acquired *lazily* on first write, so two transactions can both start, both read, then collide on upgrade and one gets `SQLITE_BUSY`/"database is locked" mid-transaction. SQLite-first: use **`BEGIN IMMEDIATE`** for any transaction that will write, so the writer lock is taken up front and contention degrades to a clean wait instead of a late failure. Pair with a documented, bounded concurrency envelope (how many write workers are safe).

### 4.2 Two overlapping timeouts — KNOB
`create_connection()` passes Python `timeout=15` (and `timeout=15` RO) while `get_connection()` sets `busy_timeout=5000` (5s). These are two different mechanisms for the same thing with different values. Pick one source of truth and document it.

### 4.3 `is_deadlocked` / `is_timedout` both map to "database is locked" — KNOB
Both predicates match the same string, so Frappe's deadlock-retry vs timeout-error paths can't be distinguished on SQLite. Fine for a POC; for critical rollouts, define retry semantics deliberately (SQLite has no true deadlock under single-writer, so most "locked" cases want bounded retry, not a deadlock error).

---

## Priority summary

| # | Finding | Tag | Severity | Non-breaking fix direction |
|---|---------|-----|----------|----------------------------|
| 1.1 | Money/Float stored as `REAL` | CORRECTNESS | Critical | Integer minor units or TEXT+Decimal for SQLite |
| 1.2 | ALTER rebuild drops indexes/constraints/defaults | CORRECTNESS | Critical | Native RENAME/DROP COLUMN (3.51); proper 12-step rebuild |
| 1.3 | DDL auto-commit emulation kills transactional migrate | CORR+PERF | High | Wrap migrations in one rollback-safe transaction |
| 1.4 | `for_update` silently a no-op | CORRECTNESS | High | `BEGIN IMMEDIATE` + document |
| 2.1 | 4–6 string/regex rewrites per query | PERF | High | Memoize transform / author in SQLite dialect |
| 2.2 | Dict-value path interpolates instead of binds | CORR+PERF | High | Named `:param` binding |
| 2.3 | Connection close/reopen on read_only toggle | PERF | Medium | Persistent RW+RO connections / `query_only` |
| 2.4 | Python UDFs (`CONCAT_WS`/regex) on row path | PERF | Medium | Native `concat_ws` (3.44+); FTS/LIKE for text |
| 2.5 | `estimate_count` = full `COUNT(*)` | PERF | Medium | `MAX(rowid)` estimate / counter / cache |
| 2.6 | Per-row datetime converters | PERF | Low-Med | Measure; lazy conversion |
| 2.7 | WAL re-asserted per connection | PERF | Low | Set once at site creation |
| 3.1 | No cache_size/mmap/temp_store/checkpoint profile | KNOB | Medium | Documented server PRAGMA profile |
| 3.2 | FK enforcement undecided | KNOB | Medium | Decide + document |
| 3.3 | STRICT tables unused | KNOB | Low-Med | Opt-in for new sites |
| 4.1 | Single-writer vs multi-worker contention | CORRECTNESS | High | `BEGIN IMMEDIATE` + concurrency envelope |
| 4.2 | Two overlapping timeouts | KNOB | Low | Single source of truth |
| 4.3 | deadlock == timeout detection | KNOB | Low | Define retry semantics |

---

## What changes if SQLite is "a serious stack for critical rollouts"

The three items that move this from "neat POC" to "trustworthy" are **1.1 (money as REAL)**, **1.2 (lossy ALTER)**, and **4.1 (write concurrency)** — those are the ones that can lose money, lose indexes/constraints silently, or fail under real concurrent load. Everything in Tier 2 is "make it fast enough to be pleasant," and Tier 3 is "give operators the knobs they expect."

The encouraging part: the bundled SQLite is **3.51**, so almost every fix here is *removing* MariaDB-era emulation (table rebuilds, the Python `CONCAT_WS`, the DDL auto-commit guard) and leaning on native, modern SQLite features — i.e. the SQLite-first path is generally *less* code, not more, and stays entirely inside the `db_type == "sqlite"` branch.

*No code was modified to produce this review.*
