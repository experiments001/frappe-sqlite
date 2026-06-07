# SQLite Backup & Restore

This document describes how to safely back up and restore Frappe sites running on SQLite, and how this differs from the MariaDB backup path.

## Safe Offline Copy Procedure

For SQLite, the database is a single file on disk (and optional WAL/shm files). The simplest and safest way to back it up is:

1. **Stop the Frappe site / ensure no writes are in progress.**
2. **Copy the `.db` file** (and `-wal`/`-shm` if WAL mode is enabled) using `shutil.copy2` or `cp`.
3. **Verify the copy** has the same size and passes `PRAGMA integrity_check`.

Example:

```python
import shutil
from pathlib import Path
import frappe

db_path = Path(frappe.db.db_path)
backup_path = Path("/safe/backup/location") / f"{frappe.local.site}.db"
shutil.copy2(db_path, backup_path)
```

> **Note:** `frappe.utils.backups.BackupGenerator.take_dump()` already handles SQLite by gzipping the `.db` file directly (see `frappe/utils/backups.py`). The test in `test_sqlite_only_runtime.py` proves that a plain file-level copy also works.

## WAL Mode Notes

- SQLite may run in **WAL mode** (Write-Ahead Logging). When WAL is active, two extra files exist alongside the `.db` file:
  - `*.db-wal`
  - `*.db-shm`
- **For a 100 % consistent backup, copy all three files together** while the database is not being written to, or perform a `PRAGMA wal_checkpoint(FULL)` before copying.
- If you only copy the `.db` file while WAL mode is active and transactions exist in the WAL, those transactions will be missing from the backup.

## Restore to New Site

1. Create a new Frappe site directory structure.
2. Place the copied `.db` file into `sites/<new_site>/db/<db_name>.db`.
3. Update `site_config.json` with the new `db_name`.
4. Start the site.

Example:

```bash
mkdir -p sites/newsite.localhost/db
cp /safe/backup/location/sqliteonly.localhost.db sites/newsite.localhost/db/_newhash.db
# update sites/newsite.localhost/site_config.json with db_name
```

## Limitations vs MariaDB Backup

| Feature | MariaDB | SQLite |
|---------|---------|--------|
| Backup format | SQL dump (`.sql.gz`) | File copy / gzip of `.db` |
| Partial backups | Supported via `--ignore-table` | Not supported natively (entire file) |
| Point-in-time recovery | Binary logs | WAL files (manual) |
| Cross-platform restore | SQL is portable | File must match SQLite version / architecture |
| Concurrent backup | `mysqldump` locks / consistency | Requires no writes during copy |
| Encryption | GPG encryption supported | Same GPG wrapper can be applied to `.db` file |

## Summary

- SQLite backups are **file-level operations**.
- Keep WAL files in mind if WAL mode is enabled.
- Test integrity with `PRAGMA integrity_check` after any restore.
