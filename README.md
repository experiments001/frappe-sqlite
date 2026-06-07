# Frappe SQLite

Frappe-compatible fork with optional SQLite support and optional host-native desktop packaging.

This repository keeps the upstream Frappe layout intact. MariaDB/PostgreSQL remain the normal defaults. SQLite is an opt-in runtime profile selected through site config or environment config.

## SQLite Profile

Phase 1 local profile:

```json
{
  "db_type": "sqlite",
  "cache_backend": "local",
  "queue_backend": "sync",
  "realtime_backend": "noop",
  "pause_scheduler": 1
}
```

SQLite runtime code lives in normal Frappe paths, mainly:

```text
frappe/database/sqlite/
frappe/search/sqlite_search.py
frappe/utils/redis_wrapper.py
frappe/utils/background_jobs.py
frappe/realtime.py
```

## Desktop

Optional desktop packaging lives under:

```text
desktop/
  shell/
  runtime/
  scripts/
```

Desktop is a consumer of the SQLite runtime. It should not define core framework behavior.

See [desktop/README.md](desktop/README.md).
