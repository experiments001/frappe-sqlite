# SQLite Site — Access & Operations Guide

Date: 2026-06-07

---

## Quick Access

| Item | Value |
|---|---|
| **Browser URL** | http://localhost:8105 |
| **Username** | Administrator |
| **Password** | admin |
| **Site name** | `sqliteonly.localhost` |

> Port 8105 on your Mac maps to port 8005 inside the container. No `/etc/hosts` edit needed — `default_site` is set so `localhost` routes directly to the SQLite site.

---

## What Is Running

### Docker container
| Item | Value |
|---|---|
| Container | `devcontainer-frappe-1` |
| Compose file | `/Users/safwan/Code/docker/fdocker/.devcontainer` |
| OrbStack UI | Group: **devcontainer** → frappe |

### Bench
| Item | Value |
|---|---|
| Bench path (host) | `/Users/safwan/Code/docker/fdocker/development/sqlitepoc` |
| Bench path (inside container) | `/workspace/development/sqlitepoc` |
| Frappe version | `16.20.0` |
| Apps installed | `frappe` only |

### Sites in this bench
| Site | DB type | Notes |
|---|---|---|
| `sqliteonly.localhost` | **SQLite** | POC site — default site |
| `sqlitepoc.localhost` | MariaDB | Reference site |

---

## SQLite Site Config

**Path:** `/workspace/development/sqlitepoc/sites/sqliteonly.localhost/site_config.json`

```json
{
  "allow_tests": true,
  "cache_backend": "local",
  "db_name": "_629808a2a7925e7e",
  "db_password": "W15cKApUJOCL6dCj",
  "db_type": "sqlite",
  "disable_async": 1,
  "encryption_key": "MJu2IBBUZSoa-TPT5jzloaWwoE4wpJuaGy6E98Nx7ws=",
  "pause_scheduler": 1,
  "queue_backend": "sync",
  "realtime_backend": "noop"
}
```

**SQLite DB file:**
```
/workspace/development/sqlitepoc/sites/sqliteonly.localhost/db/_629808a2a7925e7e.db
```

---

## Common Site Config

**Path:** `/workspace/development/sqlitepoc/sites/common_site_config.json`

Key entries relevant to this POC:

```json
{
  "default_site": "sqliteonly.localhost",
  "serve_default_site": true,
  "webserver_port": "8003",
  "redis_cache": "redis://redis-cache:6379",
  "redis_queue": "redis://redis-queue:6379"
}
```

> `default_site` routes bare `localhost` requests to `sqliteonly.localhost` so no Host header or `/etc/hosts` entry is needed.

---

## Port Map

| Inside container | Host (Mac) | Used for |
|---|---|---|
| 8003 | 8103 | Default bench web (MariaDB site) |
| 8004 | 8104 | Spare |
| **8005** | **8105** | **SQLite POC site ← use this** |

---

## How to Start the Server Manually

### 1. Exec into the container

```bash
docker exec -it devcontainer-frappe-1 bash
```

### 2. Start bench serve for SQLite site

```bash
cd /workspace/development/sqlitepoc
source env/bin/activate
bench serve --port 8005 --noreload
```

Or run in the background:

```bash
nohup bench serve --port 8005 --noreload > logs/serve-8005.log 2>&1 &
```

### 3. Open in browser

```
http://localhost:8105
```

Login: `Administrator` / `admin`

---

## How to Stop the Server

```bash
docker exec devcontainer-frappe-1 bash -c \
  "kill \$(ps aux | grep 'serve --port 8005' | grep -v grep | awk '{print \$1}')"
```

---

## Running Tests

From inside the container:

```bash
cd /workspace/development/sqlitepoc
source env/bin/activate

# Core SQLite runtime tests (works with MariaDB/Redis stopped)
bench --site sqliteonly.localhost run-tests --module frappe.tests.test_sqlite_only_runtime
```

To validate no-infra mode (stop MariaDB and Redis first):

```bash
docker stop devcontainer-mariadb-1 devcontainer-redis-cache-1 devcontainer-redis-queue-1
bench --site sqliteonly.localhost run-tests --module frappe.tests.test_sqlite_only_runtime
docker start devcontainer-mariadb-1 devcontainer-redis-cache-1 devcontainer-redis-queue-1
```

Expected: `Ran 9 integration tests — OK`

---

## SQLite-Specific Runtime Profile

This site runs with all heavy infrastructure disabled:

| System | Mode | Effect |
|---|---|---|
| Database | SQLite | No MariaDB needed |
| Cache | `local` (in-process) | No Redis needed |
| Queue | `sync` | Jobs run inline, no RQ workers |
| Realtime | `noop` | No socket.io/Redis pubsub |
| Scheduler | paused | No background periodic jobs |
| Async | disabled | All jobs synchronous |

See full limitations: `docs/SQLITE_ONLY_LIMITATIONS.md`

---

## Frappe Source (SQLite patches)

The `frappe` app in this bench is the patched SQLite fork:

```
/workspace/development/sqlitepoc/apps/frappe/
```

Key modified files:
- `frappe/database/sqlite/database.py` — connection, CONCAT_WS shim
- `frappe/database/sqlite/schema.py` — schema mutations
- `frappe/utils/redis_wrapper.py` — LocalCache with TTL
- `frappe/utils/background_jobs.py` — sync queue
- `frappe/realtime.py` — noop backend
