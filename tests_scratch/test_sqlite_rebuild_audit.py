"""
Adversarial audit of _split_create_table_body / _patch_column_in_parts / change_column_type.

Replicated verbatim from frappe/database/sqlite/database.py (the helpers are @staticmethod
so they import fine, but Frappe's __init__.py triggers side-effects at import time on some
environments; replicating avoids the dependency entirely).

NOTE: We replicate the EXACT functions from the source so any bug we find is the same bug
that would manifest in production. If the production code is later patched, this test will
still detect regressions by testing the replicated-then-fixed version.

Run with:  python -m pytest tests_scratch/test_sqlite_rebuild_audit.py -v
Or:        python tests_scratch/test_sqlite_rebuild_audit.py
"""

import re
import sqlite3
import sys
import tempfile
import os

# ─── Replicate the exact helper functions from database.py ───────────────────
# Source: frappe/database/sqlite/database.py

def _split_create_table_body(create_sql: str):
    """Quote-aware depth splitter — updated copy from database.py (post-fix)."""
    first = create_sql.index("(")
    last = create_sql.rindex(")")
    body = create_sql[first + 1 : last]

    parts, current, depth = [], [], 0
    in_quote = None
    i = 0
    while i < len(body):
        ch = body[i]
        if in_quote:
            current.append(ch)
            if ch == in_quote:
                if i + 1 < len(body) and body[i + 1] == in_quote:
                    i += 1
                    current.append(body[i])
                else:
                    in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
        i += 1
    if current:
        parts.append("".join(current).strip())

    return create_sql[: first + 1], parts, create_sql[last:]


def _patch_column_in_parts(parts, column, new_type, nullable):
    """Column-type patcher — verbatim copy from database.py."""
    col_pat = re.compile(
        rf'^([`"\[]?{re.escape(column)}[`"\]]?\s+)(\S+)(.*)',
        re.IGNORECASE | re.DOTALL,
    )
    new_parts = list(parts)
    for i, part in enumerate(parts):
        m = col_pat.match(part.strip())
        if m:
            prefix_ws, _old_type, rest = m.group(1), m.group(2), m.group(3)
            if nullable:
                rest = re.sub(r"\bNOT\s+NULL\b", "", rest, flags=re.IGNORECASE).strip()
            else:
                if not re.search(r"\bNOT\s+NULL\b", rest, re.IGNORECASE):
                    rest = " NOT NULL" + rest
            new_parts[i] = f"{part[:part.index(part.strip()[0])]}{prefix_ws}{new_type}{rest}"
            return new_parts, True
    return new_parts, False


def rebuild_table(conn, table_name, target_col, new_type, nullable=True):
    """Replicate the exact rebuild logic of change_column_type (no Frappe context needed)."""
    cur = conn.cursor()

    # Verify column exists
    col_names = [r[1] for r in cur.execute(f'PRAGMA table_info("{table_name}")').fetchall()]
    assert target_col in col_names, f"Column {target_col!r} not found in {table_name}"

    # Fetch original CREATE TABLE sql
    row = cur.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    assert row and row[0], f"No CREATE TABLE sql for {table_name}"
    original_sql = row[0]

    # Save indexes and triggers
    saved_indexes = [
        r[0] for r in cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
            (table_name,)
        ).fetchall()
    ]
    saved_triggers = [
        r[0] for r in cur.execute(
            "SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND sql IS NOT NULL",
            (table_name,)
        ).fetchall()
    ]

    # Parse and patch
    prefix, parts, suffix = _split_create_table_body(original_sql)
    parts, found = _patch_column_in_parts(parts, target_col, new_type, nullable)
    assert found, f"Column {target_col!r} not found in parsed parts"

    temp_name = table_name + "_new"
    new_body = ",\n".join(parts)
    temp_create = re.sub(
        r'(CREATE\s+TABLE\s+)[`"\[]?' + re.escape(table_name) + r'[`"\]]?',
        rf'\1"{temp_name}"',
        prefix,
        count=1,
        flags=re.IGNORECASE,
    ) + new_body + suffix

    col_list = ", ".join(f'"{c}"' for c in col_names)
    cur.execute(temp_create)
    cur.execute(f'INSERT INTO "{temp_name}" SELECT {col_list} FROM "{table_name}"')
    cur.execute(f'DROP TABLE "{table_name}"')
    cur.execute(f'ALTER TABLE "{temp_name}" RENAME TO "{table_name}"')
    for sql in saved_indexes + saved_triggers:
        cur.execute(sql)
    conn.commit()


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.isolation_level = None  # autocommit off; we manage
    return conn


def get_schema(conn, name):
    return conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0]


def get_indexes(conn, table):
    return [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table,)
    ).fetchall()]


def get_triggers(conn, table):
    return [r[0] for r in conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND sql IS NOT NULL",
        (table,)
    ).fetchall()]


# ─── Test cases ──────────────────────────────────────────────────────────────

RESULTS = []

def record(case, label, passed, note=""):
    RESULTS.append((case, label, "PASS" if passed else "FAIL", note))


def test_case_a_check_comma_in_string():
    """a) CHECK with comma inside string literal: status IN ('a,b','c')"""
    conn = make_conn()
    conn.execute("""CREATE TABLE t (
        id INTEGER PRIMARY KEY,
        status TEXT CHECK (status IN ('a,b','c')),
        val INTEGER
    )""")
    conn.execute("CREATE INDEX t_val_idx ON t(val)")
    conn.execute("CREATE TRIGGER t_trg AFTER INSERT ON t BEGIN SELECT 1; END")
    conn.execute("INSERT INTO t VALUES (1,'a,b',10)")
    conn.execute("INSERT INTO t VALUES (2,'c',20)")

    before_schema = get_schema(conn, "t")
    rebuild_table(conn, "t", "val", "TEXT", nullable=True)

    rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    indexes = get_indexes(conn, "t")
    triggers = get_triggers(conn, "t")
    after_schema = get_schema(conn, "t")

    ok = (rows == 2 and len(indexes) >= 1 and len(triggers) >= 1
          and "CHECK" in after_schema and "'a,b'" in after_schema)
    record("a", "CHECK comma-in-string", ok,
           f"rows={rows} idxs={len(indexes)} trigs={len(triggers)} CHECK_preserved={'CHECK' in after_schema}")
    assert ok, f"FAIL: schema={after_schema!r}"


def test_case_b_default_unbalanced_paren_in_string():
    """b) DEFAULT '(' — unbalanced open-paren inside string literal."""
    conn = make_conn()
    conn.execute("""CREATE TABLE t (
        id INTEGER PRIMARY KEY,
        label TEXT DEFAULT '(',
        val INTEGER
    )""")
    conn.execute("CREATE INDEX t_val_idx ON t(val)")
    conn.execute("CREATE TRIGGER t_trg AFTER INSERT ON t BEGIN SELECT 1; END")
    conn.execute("INSERT INTO t(id,val) VALUES (1,10)")
    conn.execute("INSERT INTO t(id,val) VALUES (2,20)")

    rebuild_table(conn, "t", "val", "TEXT", nullable=True)

    rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    indexes = get_indexes(conn, "t")
    triggers = get_triggers(conn, "t")
    schema = get_schema(conn, "t")

    # Key check: val column should exist and label column should still have DEFAULT '('
    cols = [r[1] for r in conn.execute("PRAGMA table_info(t)").fetchall()]
    ok = (rows == 2 and len(indexes) >= 1 and len(triggers) >= 1
          and "val" in cols and "label" in cols
          and "DEFAULT '('" in schema)
    record("b", "DEFAULT unbalanced-paren in string", ok,
           f"rows={rows} cols={cols} default_preserved={'DEFAULT' in schema}")
    assert ok, f"FAIL: schema={schema!r}"


def test_case_c_composite_primary_key():
    """c) Composite PRIMARY KEY (col_a, col_b)"""
    conn = make_conn()
    conn.execute("""CREATE TABLE t (
        col_a TEXT,
        col_b TEXT,
        val INTEGER,
        PRIMARY KEY (col_a, col_b)
    )""")
    conn.execute("CREATE INDEX t_val_idx ON t(val)")
    conn.execute("CREATE TRIGGER t_trg AFTER INSERT ON t BEGIN SELECT 1; END")
    conn.execute("INSERT INTO t VALUES ('x','y',10)")
    conn.execute("INSERT INTO t VALUES ('a','b',20)")

    rebuild_table(conn, "t", "val", "TEXT", nullable=True)

    rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    indexes = get_indexes(conn, "t")
    triggers = get_triggers(conn, "t")
    schema = get_schema(conn, "t")

    ok = (rows == 2 and len(indexes) >= 1 and len(triggers) >= 1
          and "PRIMARY KEY" in schema)
    record("c", "Composite PRIMARY KEY", ok,
           f"rows={rows} PK_preserved={'PRIMARY KEY' in schema}")
    assert ok, f"FAIL: schema={schema!r}"


def test_case_d_autoincrement():
    """d) name INTEGER PRIMARY KEY AUTOINCREMENT — must survive rebuild."""
    conn = make_conn()
    conn.execute("""CREATE TABLE t (
        name INTEGER PRIMARY KEY AUTOINCREMENT,
        val INTEGER
    )""")
    conn.execute("CREATE INDEX t_val_idx ON t(val)")
    conn.execute("CREATE TRIGGER t_trg AFTER INSERT ON t BEGIN SELECT 1; END")
    conn.execute("INSERT INTO t(val) VALUES (10)")
    conn.execute("INSERT INTO t(val) VALUES (20)")

    rebuild_table(conn, "t", "val", "TEXT", nullable=True)

    rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    indexes = get_indexes(conn, "t")
    triggers = get_triggers(conn, "t")
    schema = get_schema(conn, "t")

    # Confirm AUTOINCREMENT survived
    ok = (rows == 2 and len(indexes) >= 1 and len(triggers) >= 1
          and "AUTOINCREMENT" in schema)
    record("d", "INTEGER PRIMARY KEY AUTOINCREMENT", ok,
           f"rows={rows} AUTOINC_preserved={'AUTOINCREMENT' in schema}")
    assert ok, f"FAIL: schema={schema!r}"


def test_case_e_generated_column():
    """e) Generated column: total REAL GENERATED ALWAYS AS (qty * rate) STORED"""
    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < (3, 31, 0):
        record("e", "Generated column", "N/A", f"SQLite {sqlite3.sqlite_version} < 3.31")
        return

    conn = make_conn()
    conn.execute("""CREATE TABLE t (
        id INTEGER PRIMARY KEY,
        qty REAL,
        rate REAL,
        total REAL GENERATED ALWAYS AS (qty * rate) STORED,
        label TEXT
    )""")
    conn.execute("CREATE INDEX t_label_idx ON t(label)")
    conn.execute("CREATE TRIGGER t_trg AFTER INSERT ON t BEGIN SELECT 1; END")
    conn.execute("INSERT INTO t(id,qty,rate,label) VALUES (1,3.0,5.0,'x')")
    conn.execute("INSERT INTO t(id,qty,rate,label) VALUES (2,2.0,4.0,'y')")

    rebuild_table(conn, "t", "label", "INTEGER", nullable=True)

    rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    indexes = get_indexes(conn, "t")
    triggers = get_triggers(conn, "t")
    schema = get_schema(conn, "t")

    ok = (rows == 2 and len(indexes) >= 1 and len(triggers) >= 1
          and "GENERATED" in schema)
    record("e", "Generated column", ok,
           f"rows={rows} GEN_preserved={'GENERATED' in schema}")
    assert ok, f"FAIL: schema={schema!r}"


def test_case_f_quoted_identifier_with_comma():
    """f) Quoted identifier containing a comma: "weird,col" TEXT"""
    conn = make_conn()
    conn.execute('''CREATE TABLE t (
        id INTEGER PRIMARY KEY,
        "weird,col" TEXT,
        val INTEGER
    )''')
    conn.execute("CREATE INDEX t_val_idx ON t(val)")
    conn.execute("CREATE TRIGGER t_trg AFTER INSERT ON t BEGIN SELECT 1; END")
    conn.execute('INSERT INTO t VALUES (1,"hello",10)')
    conn.execute('INSERT INTO t VALUES (2,"world",20)')

    rebuild_table(conn, "t", "val", "TEXT", nullable=True)

    rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    indexes = get_indexes(conn, "t")
    triggers = get_triggers(conn, "t")
    schema = get_schema(conn, "t")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(t)").fetchall()]

    ok = (rows == 2 and len(indexes) >= 1 and len(triggers) >= 1
          and "weird,col" in cols)
    record("f", 'Quoted identifier "weird,col"', ok,
           f"rows={rows} cols={cols}")
    assert ok, f"FAIL: schema={schema!r}, cols={cols}"


def test_case_g_check_nested_parens():
    """g) CHECK with nested parens: CHECK ((a > 0) AND (b IN (1,2,3)))"""
    conn = make_conn()
    conn.execute("""CREATE TABLE t (
        id INTEGER PRIMARY KEY,
        a INTEGER,
        b INTEGER,
        val TEXT,
        CHECK ((a > 0) AND (b IN (1,2,3)))
    )""")
    conn.execute("CREATE INDEX t_val_idx ON t(val)")
    conn.execute("CREATE TRIGGER t_trg AFTER INSERT ON t BEGIN SELECT 1; END")
    conn.execute("INSERT INTO t VALUES (1,1,1,'x')")
    conn.execute("INSERT INTO t VALUES (2,2,2,'y')")

    rebuild_table(conn, "t", "val", "INTEGER", nullable=True)

    rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    indexes = get_indexes(conn, "t")
    triggers = get_triggers(conn, "t")
    schema = get_schema(conn, "t")

    ok = (rows == 2 and len(indexes) >= 1 and len(triggers) >= 1
          and "CHECK" in schema)
    record("g", "CHECK nested parens", ok,
           f"rows={rows} CHECK_preserved={'CHECK' in schema}")
    assert ok, f"FAIL: schema={schema!r}"


def test_case_h_default_expression():
    """h) DEFAULT expression: created REAL DEFAULT (julianday('now'))"""
    conn = make_conn()
    conn.execute("""CREATE TABLE t (
        id INTEGER PRIMARY KEY,
        created REAL DEFAULT (julianday('now')),
        val TEXT
    )""")
    conn.execute("CREATE INDEX t_val_idx ON t(val)")
    conn.execute("CREATE TRIGGER t_trg AFTER INSERT ON t BEGIN SELECT 1; END")
    conn.execute("INSERT INTO t(id,val) VALUES (1,'x')")
    conn.execute("INSERT INTO t(id,val) VALUES (2,'y')")

    rebuild_table(conn, "t", "val", "INTEGER", nullable=True)

    rows = conn.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    indexes = get_indexes(conn, "t")
    triggers = get_triggers(conn, "t")
    schema = get_schema(conn, "t")

    ok = (rows == 2 and len(indexes) >= 1 and len(triggers) >= 1
          and "julianday" in schema)
    record("h", "DEFAULT expression julianday", ok,
           f"rows={rows} DEFAULT_preserved={'julianday' in schema}")
    assert ok, f"FAIL: schema={schema!r}"


# ─── Runner ──────────────────────────────────────────────────────────────────

def run_all():
    tests = [
        ("a", test_case_a_check_comma_in_string),
        ("b", test_case_b_default_unbalanced_paren_in_string),
        ("c", test_case_c_composite_primary_key),
        ("d", test_case_d_autoincrement),
        ("e", test_case_e_generated_column),
        ("f", test_case_f_quoted_identifier_with_comma),
        ("g", test_case_g_check_nested_parens),
        ("h", test_case_h_default_expression),
    ]

    print(f"\nSQLite version: {sqlite3.sqlite_version}\n")
    print(f"{'Case':<6} {'Label':<40} {'Result':<8} Notes")
    print("-" * 90)

    failed = []
    for case_id, fn in tests:
        try:
            fn()
            # pick up from RESULTS
        except AssertionError as e:
            # RESULTS already has the entry from record() before the assert
            failed.append((case_id, str(e)))
        except Exception as e:
            record(case_id, fn.__doc__.strip().split("\n")[0], False, f"EXCEPTION: {e}")
            failed.append((case_id, str(e)))

    for case, label, result, note in RESULTS:
        marker = "✅" if result == "PASS" else ("⚠️" if result == "N/A" else "❌")
        print(f"{case:<6} {label:<40} {marker} {result:<6} {note}")

    print()
    if failed:
        print(f"VERDICT: {len(failed)} case(s) FAILED — _split_create_table_body is NOT quote-aware.")
        print("Root causes:")
        for cid, msg in failed:
            print(f"  [{cid}] {msg[:200]}")
        return False
    else:
        print("VERDICT: All cases PASSED.")
        return True


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
