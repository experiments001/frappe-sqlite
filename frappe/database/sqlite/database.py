import re
import sqlite3
import warnings
from datetime import date, datetime, time
from pathlib import Path

import frappe
from frappe.database.database import (
	TRANSACTION_DISABLED_MSG,
	Database,
	ImplicitCommitError,
)
from frappe.database.sqlite.schema import SQLiteTable
from frappe.utils import get_table_name

_PARAM_COMP = re.compile(r"%\([\w]*\)s")
IMPLICIT_COMMIT_QUERY_TYPES = frozenset(("start", "alter", "drop", "create", "truncate"))


class SQLiteExceptionUtil:
	ProgrammingError = sqlite3.ProgrammingError
	TableMissingError = sqlite3.OperationalError
	OperationalError = sqlite3.OperationalError
	InternalError = sqlite3.InternalError
	SQLError = sqlite3.OperationalError
	DataError = sqlite3.DataError

	@staticmethod
	def is_deadlocked(e: sqlite3.Error) -> bool:
		return "database is locked" in str(e)

	@staticmethod
	def is_timedout(e: sqlite3.Error) -> bool:
		return "database is locked" in str(e)

	@staticmethod
	def is_read_only_mode_error(e: sqlite3.Error) -> bool:
		return "attempt to write a readonly database" in str(e)

	@staticmethod
	def is_table_missing(e: sqlite3.Error) -> bool:
		return "no such table" in str(e)

	@staticmethod
	def is_missing_column(e: sqlite3.Error) -> bool:
		return "no such column" in str(e)

	@staticmethod
	def is_duplicate_fieldname(e: sqlite3.Error) -> bool:
		return "duplicate column name" in str(e)

	@staticmethod
	def is_duplicate_entry(e: sqlite3.Error) -> bool:
		return "UNIQUE constraint failed" in str(e)

	@staticmethod
	def is_access_denied(e: sqlite3.Error) -> bool:
		return "access denied" in str(e)

	@staticmethod
	def cant_drop_field_or_key(e: sqlite3.Error) -> bool:
		return "cannot drop" in str(e)

	@staticmethod
	def is_syntax_error(e: sqlite3.Error) -> bool:
		return "syntax error" in str(e)

	@staticmethod
	def is_statement_timeout(e: sqlite3.Error) -> bool:
		return "statement timeout" in str(e)

	@staticmethod
	def is_data_too_long(e: sqlite3.Error) -> bool:
		return "string or blob too big" in str(e)

	@staticmethod
	def is_db_table_size_limit(e: sqlite3.Error) -> bool:
		return "too many columns" in str(e)

	@staticmethod
	def is_primary_key_violation(e: sqlite3.IntegrityError) -> bool:
		if hasattr(e, "sqlite_errorcode"):
			return e.sqlite_errorcode == 1555
		return "UNIQUE constraint failed" in str(e)

	@staticmethod
	def is_unique_key_violation(e: sqlite3.IntegrityError) -> bool:
		if hasattr(e, "sqlite_errorcode"):
			return e.sqlite_errorcode == 2067
		return "UNIQUE constraint failed" in str(e)

	@staticmethod
	def is_interface_error(e: sqlite3.Error):
		return isinstance(e, sqlite3.InterfaceError)

	@staticmethod
	def is_nested_transaction_error(e: sqlite3.Error):
		return "cannot start a transaction within a transaction" in str(e)


class SQLiteDatabase(SQLiteExceptionUtil, Database):
	REGEX_CHARACTER = "regexp"
	default_port = None
	MAX_ROW_SIZE_LIMIT = None

	# Single source of truth for write-lock wait time (fix 4.2).
	# PRAGMA busy_timeout is the actual SQLite mechanism; Python's timeout= is set
	# to a slightly higher value so the OS doesn't kill the connection before SQLite
	# has a chance to retry.
	_BUSY_TIMEOUT_MS = 5000  # milliseconds — used for PRAGMA busy_timeout
	_CONNECT_TIMEOUT_S = 6   # seconds — Python sqlite3 connect() timeout (must be > busy_timeout/1000)

	def get_connection(self, read_only: bool = False):
		conn = self.create_connection(read_only)
		conn.create_function("regexp", 2, regexp)
		conn.create_function("regexp_replace", 3, regexp_replace)
		# Per-connection pragmas (NOT journal_mode — that persists in the DB header
		# and is set once at site creation in setup_db.py; re-asserting it every
		# connect triggers avoidable checkpoint/IO work).
		cursor = conn.cursor()
		cursor.execute(f"PRAGMA synchronous = NORMAL")
		cursor.execute(f"PRAGMA busy_timeout = {self._BUSY_TIMEOUT_MS}")
		# Performance profile (fix 3.1)
		cursor.execute("PRAGMA cache_size = -32768")     # 32 MB page cache
		cursor.execute("PRAGMA mmap_size = 134217728")   # 128 MB memory-mapped IO
		cursor.execute("PRAGMA temp_store = MEMORY")     # sorts/temp B-trees in RAM
		cursor.execute("PRAGMA wal_autocheckpoint = 1000")  # checkpoint every ~4 MB of WAL
		# Foreign keys: OFF by design — Frappe relies on app-level integrity (fix 3.2)
		cursor.execute("PRAGMA foreign_keys = OFF")
		cursor.close()
		return conn

	def create_connection(self, read_only: bool = False):
		db_path = self.get_db_path()
		sqlite3.register_converter("timestamp", lambda x: datetime.fromisoformat(x.decode()))
		sqlite3.register_converter("date", lambda x: date.fromisoformat(x.decode()))
		sqlite3.register_converter("time", lambda x: time.fromisoformat(x.decode()))
		if read_only:
			conn = sqlite3.connect(
				f"file:{db_path}?mode=ro",
				uri=True,
				detect_types=sqlite3.PARSE_DECLTYPES,
				timeout=self._CONNECT_TIMEOUT_S,
			)
		else:
			conn = sqlite3.connect(
				db_path,
				detect_types=sqlite3.PARSE_DECLTYPES,
				timeout=self._CONNECT_TIMEOUT_S,
			)

		# CONCAT_WS is native in SQLite 3.44+ — no Python shim needed (fix 2.4)
		return conn

	def get_db_path(self):
		return Path(frappe.get_site_path()) / "db" / f"{self.cur_db_name}.db"

	def set_execution_timeout(self, seconds: int):
		self.sql(f"PRAGMA busy_timeout = {int(seconds) * 1000}")

	def setup_type_map(self):
		self.db_type = "sqlite"
		self.type_map = {
			"Currency": ("REAL", None),
			"Int": ("INTEGER", None),
			"Long Int": ("INTEGER", None),
			"Float": ("REAL", None),
			"Percent": ("REAL", None),
			"Check": ("INTEGER", None),
			"Small Text": ("TEXT", None),
			"Long Text": ("TEXT", None),
			"Code": ("TEXT", None),
			"Text Editor": ("TEXT", None),
			"Markdown Editor": ("TEXT", None),
			"HTML Editor": ("TEXT", None),
			"Date": ("DATE", None),
			"Datetime": ("TIMESTAMP", None),
			"Time": ("TIME", None),
			"Text": ("TEXT", None),
			"Data": ("TEXT", None),
			"Link": ("TEXT", None),
			"Dynamic Link": ("TEXT", None),
			"Password": ("TEXT", None),
			"Select": ("TEXT", None),
			"Rating": ("REAL", None),
			"Read Only": ("TEXT", None),
			"Attach": ("TEXT", None),
			"Attach Image": ("TEXT", None),
			"Signature": ("TEXT", None),
			"Color": ("TEXT", None),
			"Barcode": ("TEXT", None),
			"Geolocation": ("TEXT", None),
			"Duration": ("REAL", None),
			"Icon": ("TEXT", None),
			"Phone": ("TEXT", None),
			"Autocomplete": ("TEXT", None),
			"JSON": ("TEXT", None),
		}

	def get_database_size(self):
		"""Return database size in MB."""
		import os

		return os.path.getsize(self.get_db_path()) / (1024 * 1024)

	def _clean_up(self):
		pass

	@staticmethod
	def escape(s, percent=True):
		"""Escape quotes and percent in given string."""
		s = s.replace("'", "''")
		if percent:
			s = s.replace("%", "%%")
		return "'" + s + "'"

	@staticmethod
	def is_type_number(code):
		return code in (sqlite3.NUMERIC, sqlite3.INTEGER, sqlite3.REAL)

	@staticmethod
	def is_type_datetime(code):
		return code == sqlite3.TEXT

	def rename_table(self, old_name: str, new_name: str) -> list | tuple:
		old_name = get_table_name(old_name)
		new_name = get_table_name(new_name)
		return self.sql(f"ALTER TABLE `{old_name}` RENAME TO `{new_name}`")

	def describe(self, doctype: str) -> list | tuple:
		table_name = get_table_name(doctype)
		return self.sql(f"PRAGMA table_info(`{table_name}`)")

	# ── helpers for change_column_type ──────────────────────────────────────

	@staticmethod
	def _split_create_table_body(create_sql: str) -> tuple[str, list[str], str]:
		"""Split CREATE TABLE sql into prefix, list of column/constraint clauses,
		and suffix.  Splits on depth-0 commas only so nested parens (CHECK, etc.)
		are preserved intact.

		Returns (prefix, parts, suffix) where prefix ends with '(' and suffix
		starts with ')'.
		"""
		first = create_sql.index("(")
		last = create_sql.rindex(")")
		body = create_sql[first + 1 : last]

		parts, current, depth = [], [], 0
		for ch in body:
			if ch == "(":
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
		if current:
			parts.append("".join(current).strip())

		return create_sql[: first + 1], parts, create_sql[last:]

	@staticmethod
	def _patch_column_in_parts(
		parts: list[str], column: str, new_type: str, nullable: bool
	) -> tuple[list[str], bool]:
		"""Find the clause for *column* in *parts* and replace its type token.
		Also enforces nullability: adds/removes NOT NULL based on *nullable*.
		Returns (new_parts, found_flag).
		"""
		# Matches: optional-quote column-name optional-quote whitespace TYPE
		col_pat = re.compile(
			rf'^([`"\[]?{re.escape(column)}[`"\]]?\s+)(\S+)(.*)',
			re.IGNORECASE | re.DOTALL,
		)
		new_parts = list(parts)
		for i, part in enumerate(parts):
			m = col_pat.match(part.strip())
			if m:
				prefix_ws, _old_type, rest = m.group(1), m.group(2), m.group(3)
				# Adjust NOT NULL in the constraint tail
				if nullable:
					rest = re.sub(r"\bNOT\s+NULL\b", "", rest, flags=re.IGNORECASE).strip()
				else:
					if not re.search(r"\bNOT\s+NULL\b", rest, re.IGNORECASE):
						rest = " NOT NULL" + rest
				new_parts[i] = f"{part[:part.index(part.strip()[0])]}{prefix_ws}{new_type}{rest}"
				return new_parts, True
		return new_parts, False

	def change_column_type(
		self, doctype: str, column: str, type: str, nullable: bool = False
	) -> list | tuple:
		"""Change a column's type while preserving the full schema.

		Uses the original CREATE TABLE SQL from sqlite_master as the source of
		truth so PRIMARY KEY, AUTOINCREMENT, DEFAULT values, CHECK constraints,
		and all table-level constraints survive the rebuild.  Indexes and
		triggers are saved separately and recreated after the rename.

		This is the SQLite-recommended 12-step procedure adapted for Frappe.
		"""
		table_name = get_table_name(doctype)
		temp_table = f"{table_name}_new"

		# 1. Verify column exists
		col_names = [c["name"] for c in self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)]
		if column not in col_names:
			raise frappe.InvalidColumnName(f"Column {column} does not exist in table {table_name}")

		# 2. Fetch the original CREATE TABLE SQL — this carries PK, AUTOINCREMENT,
		#    DEFAULT, CHECK, and all table-level constraints that PRAGMA table_info
		#    does NOT return.
		original_sql_rows = self.sql(
			"SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
			(table_name,),
			as_dict=1,
		)
		if not original_sql_rows or not original_sql_rows[0]["sql"]:
			raise frappe.ValidationError(f"Cannot find CREATE TABLE sql for {table_name}")
		original_sql = original_sql_rows[0]["sql"]

		# 3. Parse the body, patch the target column's type and nullability
		prefix, parts, suffix = self._split_create_table_body(original_sql)
		parts, found = self._patch_column_in_parts(parts, column, type, nullable)
		if not found:
			raise frappe.InvalidColumnName(
				f"Column {column} found in PRAGMA but not in CREATE TABLE sql — schema inconsistency"
			)

		# 4. Build CREATE TABLE for the temp table (substitute name)
		new_body = ",\n".join(parts)
		# Replace the original table name in the CREATE TABLE header with temp_table
		temp_create = re.sub(
			r"(CREATE\s+TABLE\s+)[`\"\[]?" + re.escape(table_name) + r"[`\"\]]?",
			rf'\1`{temp_table}`',
			prefix,
			count=1,
			flags=re.IGNORECASE,
		) + new_body + suffix

		# 5. Save all indexes and triggers BEFORE the drop
		saved_indexes = [
			row["sql"]
			for row in self.sql(
				"SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
				(table_name,),
				as_dict=1,
			)
		]
		saved_triggers = [
			row["sql"]
			for row in self.sql(
				"SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name=? AND sql IS NOT NULL",
				(table_name,),
				as_dict=1,
			)
		]

		# 6–9. Create temp, copy, drop original, rename
		self.sql_ddl(temp_create)
		col_list = ", ".join(f"`{c}`" for c in col_names)
		self.sql_ddl(f"INSERT INTO `{temp_table}` SELECT {col_list} FROM `{table_name}`")
		self.sql_ddl(f"DROP TABLE `{table_name}`")
		self.sql_ddl(f"ALTER TABLE `{temp_table}` RENAME TO `{table_name}`")

		# 10–11. Restore indexes and triggers
		for sql_stmt in saved_indexes + saved_triggers:
			self.sql_ddl(sql_stmt)

	def rename_column(self, doctype: str, old_column_name: str, new_column_name: str):
		"""Rename a column using native ALTER TABLE … RENAME COLUMN (SQLite 3.25+).
		Preserves all indexes, defaults, and constraints automatically."""
		table_name = get_table_name(doctype)

		# Verify column exists
		column_exists = any(
			col["name"] == old_column_name
			for col in self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)
		)
		if not column_exists:
			raise frappe.InvalidColumnName(f"Column {old_column_name} does not exist in table {table_name}")

		# Native rename — no rebuild, no index loss (SQLite 3.25+)
		self.sql(
			f"ALTER TABLE `{table_name}` RENAME COLUMN `{old_column_name}` TO `{new_column_name}`"
		)

	def create_auth_table(self):
		self.sql_ddl(
			"""CREATE TABLE IF NOT EXISTS `__Auth` (
				`doctype` TEXT NOT NULL,
				`name` TEXT NOT NULL,
				`fieldname` TEXT NOT NULL,
				`password` TEXT NOT NULL,
				`encrypted` INTEGER NOT NULL DEFAULT 0,
				PRIMARY KEY (`doctype`, `name`, `fieldname`)
			)"""
		)

	def create_global_search_table(self):
		if "__global_search" not in self.get_tables():
			self.sql(
				"""CREATE VIRTUAL TABLE __global_search USING FTS5(
				doctype,
				name,
				title,
				content,
				route,
				published
				)"""
			)

	def create_user_settings_table(self):
		self.sql_ddl(
			"""CREATE TABLE IF NOT EXISTS __UserSettings (
			`user` TEXT NOT NULL,
			`doctype` TEXT NOT NULL,
			`data` TEXT,
			UNIQUE(user, doctype)
			)"""
		)

	@staticmethod
	def get_on_duplicate_update():
		return "ON CONFLICT DO UPDATE SET "

	def get_table_columns_description(self, table_name):
		"""Return list of columns with descriptions."""
		return self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)

	def get_column_type(self, doctype, column):
		"""Return column type from database."""
		table_name = get_table_name(doctype)
		result = self.sql(f"PRAGMA table_info(`{table_name}`)", as_dict=1)
		for row in result:
			if row["name"] == column:
				return row["type"]
		return None

	def has_index(self, table_name, index_name):
		return self.sql(f"SELECT * FROM pragma_index_list(`{table_name}`) WHERE name = '{index_name}'")

	def get_column_index(self, table_name: str, fieldname: str, unique: bool = False) -> frappe._dict | None:
		"""Check if column exists for a specific fields in specified order."""
		indexes = self.sql(f"PRAGMA index_list(`{table_name}`)", as_dict=True)
		for index in indexes:
			index_info = self.sql(f"PRAGMA index_info(`{index['name']}`)", as_dict=True)
			if index_info and index_info[0]["name"] == fieldname:
				return index

	def add_index(self, doctype: str, fields: list, index_name: str | None = None):
		"""Creates an index with given fields if not already created."""

		from frappe.custom.doctype.property_setter.property_setter import (
			make_property_setter,
		)

		# We can't specify the length of the index in SQLite
		fields = [re.sub(r"\(.*?\)", "", field) for field in fields]

		index_name = index_name or self.get_index_name(fields)
		table_name = get_table_name(doctype)
		# No explicit commit needed — DDL is transactional on SQLite
		self.sql(f"CREATE INDEX IF NOT EXISTS `{index_name}` ON `{table_name}` ({', '.join(fields)})")

		# Ensure that DB migration doesn't clear this index, assuming this is manually added
		# via code or console.
		if len(fields) == 1 and not (frappe.flags.in_install or frappe.flags.in_migrate):
			make_property_setter(
				doctype,
				fields[0],
				property="search_index",
				value="1",
				property_type="Check",
				for_doctype=False,  # Applied on docfield
			)

	def add_unique(self, doctype, fields, constraint_name=None):
		"""Creates unique constraint on fields."""
		if isinstance(fields, str):
			fields = [fields]
		if not constraint_name:
			constraint_name = f"unique_{'_'.join(fields)}"
		table_name = get_table_name(doctype)

		columns = ", ".join(fields)
		sql_create_unique = (
			f"CREATE UNIQUE INDEX IF NOT EXISTS `{constraint_name}` ON `{table_name}` ({columns})"
		)
		# No explicit commit needed — DDL is transactional on SQLite
		self.sql(sql_create_unique)

	def updatedb(self, doctype, meta=None):
		"""Syncs a `DocType` to the table."""
		res = self.sql("SELECT issingle FROM `tabDocType` WHERE name=%s", (doctype,))
		if not res:
			raise Exception(f"Wrong doctype {doctype} in updatedb")

		if not res[0][0]:
			db_table = SQLiteTable(doctype, meta)
			db_table.validate()
			db_table.sync()
			self.commit()

	def get_database_list(self):
		return [self.db_name]

	def get_tables(self, cached=True):
		"""Return list of tables."""
		to_query = not cached

		if cached:
			tables = frappe.cache.get_value("db_tables")
			to_query = not tables

		if to_query:
			tables = self.sql("SELECT name FROM sqlite_master WHERE type='table';", pluck=True)
			frappe.cache.set_value("db_tables", tables)

		return tables

	def get_row_size(self, doctype: str) -> int:
		"""Get estimated max row size of any table in bytes."""
		raise NotImplementedError("SQLite does not support getting row size directly.")

	# Compiled once: converts %(name)s → :name for sqlite3 named binding
	_NAMED_PARAM_RE = re.compile(r"%\((\w+)\)s")

	def execute_query(self, query, values=None):
		"""Execute query with proper parameter binding.

		For positional params (list/tuple): replace %s → ? and bind normally.
		For named params (dict): replace %(name)s → :name and let sqlite3 bind
		the dict natively.  This keeps SQLite's prepared-statement cache warm
		(every call with the same query template reuses the compiled bytecode)
		and eliminates the old string-interpolation path that was both a SQL
		injection surface and a cache-killer.
		"""
		query = query.replace("%s", "?")

		if isinstance(values, dict):
			# Convert %(name)s → :name and bind via sqlite3 native named params
			query = self._NAMED_PARAM_RE.sub(r":\1", query)
			return self._cursor.execute(query, values)

		return self._cursor.execute(query, values or ())

	def sql(self, *args, **kwargs):
		if args:
			# since tuple is immutable
			args = list(args)
			args[0] = modify_query(args[0])
			args = tuple(args)
		elif kwargs.get("query"):
			kwargs["query"] = modify_query(kwargs.get("query"))

		return super().sql(*args, **kwargs)

	def sql_ddl(self, query, *args, **kwargs):
		"""Execute DDL query.

		SQLite DDL is fully transactional — CREATE/ALTER/DROP can run inside
		BEGIN…COMMIT and roll back cleanly.  We intentionally do NOT auto-commit
		around DDL here; the caller owns the transaction boundary.  This lets a
		multi-step migration (e.g. DocType sync) either fully apply or fully roll
		back, which is the opposite of the MariaDB-era behaviour this replaced.
		"""
		# Only execute the DDL; do not force a commit.
		# (The base sql_ddl calls self.commit() then self.sql() — we bypass that
		#  by calling self.sql() directly here so DDL stays in the current txn.)
		self.sql(query, *args, **kwargs)

	def begin(self, *, read_only=False):
		if read_only or frappe.flags.read_only:
			if self._conn:
				self._conn.close()
			self._conn = self.get_connection(read_only=True)
			self._cursor = self._conn.cursor()
			self.read_only = True

		elif hasattr(self, "read_only") and self.read_only:
			self._conn.close()
			self._conn = self.get_connection()
			self._cursor = self._conn.cursor()
			self.read_only = False

		try:
			if getattr(self, "read_only", False):
				# Read-only: deferred is fine; no write lock needed
				self.sql("BEGIN")
			else:
				# Write transactions use IMMEDIATE so the write lock is acquired
				# up-front.  This prevents "database is locked" errors that occur
				# with deferred BEGIN when two workers both read then try to write
				# (late lock-upgrade collision under WAL + multiple gunicorn workers).
				# SQLite's single-writer model means write contention degrades to a
				# clean wait (busy_timeout) instead of a mid-transaction failure.
				self.sql("BEGIN IMMEDIATE")
		except sqlite3.OperationalError as e:
			if not self.is_nested_transaction_error(e):
				raise e

	def commit(self, chain=None):
		"""Commit current transaction. Calls SQL `COMMIT`."""
		if not self._conn:
			self.connect()

		if self._disable_transaction_control:
			warnings.warn(message=TRANSACTION_DISABLED_MSG, stacklevel=2)
			return

		self.before_rollback.reset()
		self.after_rollback.reset()

		self.before_commit.run()

		self._conn.commit()
		self.transaction_writes = 0
		self.begin()  # explicitly start a new transaction

		self.after_commit.run()

	def rollback(self, *, save_point=None, chain=None):
		"""`ROLLBACK` current transaction. Optionally rollback to a known save_point."""
		if not self._conn:
			self.connect()
		if save_point:
			self.sql(f"rollback to savepoint {save_point}")
		elif not self._disable_transaction_control:
			self.before_commit.reset()
			self.after_commit.reset()

			self.before_rollback.run()

			self._conn.rollback()
			self.begin()

			self.after_rollback.run()
		else:
			warnings.warn(message=TRANSACTION_DISABLED_MSG, stacklevel=2)

	def get_db_table_columns(self, table) -> list[str]:
		"""Return list of column names from given table."""
		key = f"table_columns::{table}"
		columns = frappe.client_cache.get_value(key)
		if columns is None:
			columns = self.sql(f"PRAGMA table_info(`{table}`)", as_dict=True)
			columns = [col["name"] for col in columns]

			if columns:
				frappe.cache.set_value(key, columns)

		return columns

	def estimate_count(self, doctype: str):
		"""Get estimated count of total rows in a table."""
		from frappe.utils.data import cint

		table = get_table_name(doctype)
		try:
			if count := self.sql(f"SELECT COUNT(*) FROM `{table}`"):
				return cint(count[0][0])
		except sqlite3.OperationalError as e:
			if not self.is_table_missing(e):
				raise
		return 0

	def truncate(self, doctype: str):
		"""Truncate a table."""
		table = get_table_name(doctype)
		self.sql_ddl(f"DELETE FROM `{table}`")
		self.sql_ddl(f"DELETE FROM sqlite_sequence WHERE name='{table}'")

	def check_implicit_commit(self, query: str, query_type: str):
		"""SQLite DDL is fully transactional — no implicit commit on DDL.
		This override intentionally does nothing; DDL stays in the current
		transaction and will roll back cleanly if the migration fails.
		(MariaDB/Postgres raise ImplicitCommitError here because their DDL
		auto-commits; SQLite doesn't have that constraint.)
		"""
		pass  # no-op: DDL is transactional on SQLite


def modify_query(query):
	"""
	Modifies query according to the requirements of SQLite
	"""
	# Replace ` with " for definitions
	query = str(query)
	query = query.replace("`", '"')
	query = replace_locate_with_instr(query)

	# Select from requires ""
	if re.search("from tab", query, flags=re.IGNORECASE):
		query = re.sub("from tab([a-zA-Z]*)", r'from "tab\1"', query, flags=re.IGNORECASE)

	return query


def replace_locate_with_instr(query: str) -> str:
	# instr is the locate equivalent in SQLite
	if re.search(r"locate\(", query, flags=re.IGNORECASE):
		query = re.sub(r"locate\(([^,]+),([^)]+)\)", r"instr(\2, \1)", query, flags=re.IGNORECASE)
	return query


def regexp(expr: str, item: str) -> bool:
	"""
	Define regexp implementation for SQLite manually

	Although it works in the CLI - doesn't work through python
	"""
	return re.search(expr, item) is not None


def regexp_replace(item: str, pattern: str, repl: str) -> str:
	"""
	Define regexp_replace implementation for SQLite
	"""
	return re.sub(pattern, repl, item)
