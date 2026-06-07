# SQLite-Only Frappe POC Agent Handoff

Date: 2026-06-07

## Purpose

This handoff documents the current state of the SQLite-only Frappe POC work so another agent can continue without rediscovering the environment.

The immediate goal is to use a normal Docker Frappe bench as a control environment, then implement and validate a lightweight local Frappe runtime path that can eventually run with SQLite plus minimal/no Redis services for single-process development use.

## Key Repositories And Paths

### Codex Workspace

```text
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground
```

Important files:

```text
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/sqlite-only-frappe-poc-agent-prompt.md
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-playground
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc
```

### Frappe POC Branch Checkout

Host path:

```text
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc
```

Branch:

```text
poc/sqlite-only-runtime-plan
```

Current tracked source state:

```text
Base branch: version-16
Frappe version: 16.20.0
```

Current untracked docs in this checkout:

```text
docs/sqlite-only-runtime-poc-plan.md
docs/sqlite-only-runtime-agent-handoff.md
```

### Docker/Frappe Development Root

Host path:

```text
/Users/safwan/Code/docker/fdocker
```

Dev benches live under:

```text
/Users/safwan/Code/docker/fdocker/development
```

Inside the Frappe container this maps to:

```text
/workspace/development
```

### Copied Source Inside Docker Workspace

Host path:

```text
/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-source
```

Container path:

```text
/workspace/development/frappe-sqlite-source
```

Branch:

```text
poc/sqlite-only-runtime-plan
```

This source was copied from the Codex workspace Frappe checkout so `bench init` could use a local `--frappe-path` inside the mounted Docker workspace.

### New Control Bench

Host path:

```text
/Users/safwan/Code/docker/fdocker/development/sqlitepoc
```

Container path:

```text
/workspace/development/sqlitepoc
```

Site:

```text
sqlitepoc.localhost
```

Administrator password used:

```text
admin
```

MariaDB root credentials used:

```text
username: root
password: 123
```

## Docker State

Docker services were started from:

```text
/Users/safwan/Code/docker/fdocker
```

Running containers verified:

```text
devcontainer-frappe-1       frappe/bench:latest
devcontainer-mariadb-1      mariadb:10.11
devcontainer-redis-cache-1  redis:alpine
devcontainer-redis-queue-1  redis:alpine
```

Useful container command prefix:

```bash
docker exec devcontainer-frappe-1 bash -lc '<command>'
```

The Frappe container has:

```text
bench: /home/frappe/.local/bin/bench
bench version: 5.28.0
python: 3.14.2
node: 24.12.0
yarn: 1.22.22
```

Service checks already passed:

```bash
redis-cli -h redis-cache ping
redis-cli -h redis-queue ping
mariadb -h mariadb -uroot -p123 -e "select version();"
```

## Existing Benches Used As References

Under:

```text
/Users/safwan/Code/docker/fdocker/development
```

Reference benches inspected:

```text
ainative
16
edge16
```

They all use the same service pattern:

```json
{
  "db_host": "mariadb",
  "redis_cache": "redis://redis-cache:6379",
  "redis_queue": "redis://redis-queue:6379",
  "redis_socketio": "redis://redis-queue:6379"
}
```

Observed ports:

```text
16:       webserver_port 8000, socketio_port 9000
edge16:   webserver_port 8001, socketio_port 9001
ainative: webserver_port 8002, socketio_port 9002
sqlitepoc uses 8003 / 9003
```

## `sqlitepoc` Current Config

File:

```text
/Users/safwan/Code/docker/fdocker/development/sqlitepoc/sites/common_site_config.json
```

Verified contents:

```json
{
  "background_workers": 1,
  "db_host": "mariadb",
  "file_watcher_port": "6790",
  "frappe_user": "frappe",
  "gunicorn_workers": 17,
  "live_reload": true,
  "rebase_on_pull": false,
  "redis_cache": "redis://redis-cache:6379",
  "redis_queue": "redis://redis-queue:6379",
  "redis_socketio": "redis://redis-queue:6379",
  "restart_supervisor_on_update": false,
  "restart_systemd_on_update": false,
  "serve_default_site": true,
  "shallow_clone": true,
  "socketio_port": "9003",
  "use_redis_auth": false,
  "webserver_port": "8003"
}
```

## Commands Already Run

### Start Docker Services

```bash
cd /Users/safwan/Code/docker/fdocker
docker compose -f .devcontainer/docker-compose.yml up -d mariadb redis-cache redis-queue frappe
```

Note: running this from `/Users/safwan/Code/docker/fdocker` created/used `devcontainer-*` containers, not the older `fdocker_devcontainer-*` containers.

### Copy Local Frappe Branch Into Container Workspace

```bash
docker cp \
  /Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc \
  devcontainer-frappe-1:/workspace/development/frappe-sqlite-source
```

### Failed First Bench Init

Attempt:

```bash
cd /workspace/development
bench init sqlitepoc \
  --frappe-path /workspace/development/frappe-sqlite-source \
  --frappe-branch poc/sqlite-only-runtime-plan \
  --python python3 \
  --skip-assets \
  --verbose
```

Failure:

```text
/bin/sh: 1: redis-server: not found
subprocess.CalledProcessError: Command 'redis-server --version' returned non-zero exit status 127.
```

Cause:

The `frappe/bench:latest` image used here does not include a local `redis-server` binary. Bench tries to generate Redis config by calling `redis-server --version`.

Lesson:

Use `--skip-redis-config-generation` in this devcontainer and then set Redis URLs manually to the Docker services.

The partial failed bench was preserved by renaming it to a timestamped failed-init directory.

### Successful Bench Init

```bash
cd /workspace/development
bench init sqlitepoc \
  --frappe-path /workspace/development/frappe-sqlite-source \
  --frappe-branch poc/sqlite-only-runtime-plan \
  --python python3 \
  --skip-assets \
  --skip-redis-config-generation \
  --verbose
```

Result:

```text
SUCCESS: Bench sqlitepoc initialized
```

### Configure New Bench

```bash
cd /workspace/development/sqlitepoc
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench set-config -g webserver_port 8003
bench set-config -g socketio_port 9003
bench set-config -g file_watcher_port 6790
bench set-config -g serve_default_site true
bench set-config -g use_redis_auth false
bench set-config -g background_workers 1
```

### Create Site

```bash
cd /workspace/development/sqlitepoc
bench new-site sqlitepoc.localhost \
  --mariadb-root-username root \
  --mariadb-root-password 123 \
  --admin-password admin \
  --no-mariadb-socket
```

Result:

```text
Installing frappe...
Updating DocTypes for frappe: 100%
Creating Workspace Sidebars
Creating Desktop Icons
Updating Dashboard for frappe
*** Scheduler is disabled ***
```

Note:

`--no-mariadb-socket` is deprecated. Future agents should prefer:

```bash
--mariadb-user-host-login-scope='%'
```

if needed.

### Validate App List

```bash
cd /workspace/development/sqlitepoc
bench --site sqlitepoc.localhost list-apps
```

Result:

```text
frappe 16.20.0 poc/sqlite-only-runtime-plan
```

### Validate Migrate

```bash
cd /workspace/development/sqlitepoc
bench --site sqlitepoc.localhost migrate
```

Result:

```text
Migrating sqlitepoc.localhost
Updating DocTypes for frappe: 100%
Syncing jobs...
Syncing fixtures...
Syncing dashboards...
Updating Dashboard for frappe
...
Queued rebuilding of search index for sqlitepoc.localhost
```

### Validate DB Access

```bash
cd /workspace/development/sqlitepoc
bench --site sqlitepoc.localhost execute frappe.db.get_value --args "[\"User\", \"Administrator\", \"name\"]"
```

Result:

```text
Administrator
```

### Validate Document API

A `bench console` smoke inserted a `ToDo` document.

Observed output:

```text
db_type mariadb
<ToDo: doctype=ToDo qkss6joi8d>
todo qkss6joi8d
```

This confirms the control bench is currently a normal MariaDB-backed Frappe bench. That is intentional: it proves the copied branch/bench/site can run before applying SQLite-only runtime patches.

### Build Assets

```bash
cd /workspace/development/sqlitepoc
bench build --app frappe
```

Result:

```text
DONE Total Build Time: 13.577s
Compiling translations for frappe
```

### Internal HTTP Check

Temporary server command:

```bash
cd /workspace/development/sqlitepoc
bench serve --port 8003 --noreload
```

Internal container check:

```bash
curl -I --max-time 10 -H "Host: sqlitepoc.localhost" http://127.0.0.1:8003/login
```

Result:

```text
HTTP/1.1 200 OK
Server: Werkzeug/3.1.6 Python/3.14.2
Content-Type: text/html; charset=utf-8
X-Page-Name: login
```

Guest call to non-whitelisted method:

```bash
curl -sS --max-time 10 -H "Host: sqlitepoc.localhost" \
  http://127.0.0.1:8003/api/method/frappe.auth.get_logged_user
```

Result:

```text
PermissionError / Method Not Allowed
```

This is expected for a guest request.

## Known Issue: Host Port Check

Host-side curl failed:

```bash
curl -I -H "Host: sqlitepoc.localhost" http://127.0.0.1:8103/login
```

Failure:

```text
Failed to connect to 127.0.0.1 port 8103
```

But the same endpoint worked inside the container at port `8003`.

Current interpretation:

Frappe app health is good. Host port routing or Docker context/network exposure needs a separate check.

Next agent should inspect:

```bash
docker port devcontainer-frappe-1
docker inspect devcontainer-frappe-1
docker context ls
```

If Docker socket permissions or context flip between OrbStack and Docker Desktop, re-check before assuming app failure.

## Current Status

Completed:

- Docker services are up.
- New control bench exists.
- Bench uses the copied Frappe branch.
- Site creation succeeded.
- Migrate succeeded.
- Asset build succeeded.
- Basic DB and Document API smoke succeeded.
- Internal `/login` returned 200.

Not completed:

- Browser login validation from host.
- SQLite-only patches.
- SQLite site creation using the new local runtime flags.
- Local cache backend.
- Sync queue backend.
- Realtime noop backend.
- Runner/tests for SQLite-only mode.

## Retry / Review Rule

If the next agent hits several errors or repeats the same class of failure more than twice, stop and review before continuing.

Required review questions:

1. Is the failing layer Docker networking, bench config, Frappe DB, cache, queue, realtime, or frontend assets?
2. Is the current failure in the control MariaDB bench or in the SQLite-only POC path?
3. Are we still using the intended branch and bench?
4. Did a retry leave partial state that should be preserved/renamed before another attempt?
5. Can the next step be validated with a smaller smoke command before a long bench command?

Do not keep retrying `bench init`, `bench new-site`, or asset builds blindly.

## Next Plan For Agents

### Phase 1: Stabilize Control Bench Access

Goal:

Make the normal MariaDB-backed control bench reachable and testable.

Commands:

```bash
docker ps
docker port devcontainer-frappe-1
docker exec devcontainer-frappe-1 bash -lc 'cd /workspace/development/sqlitepoc && bench serve --port 8003 --noreload'
```

In another shell:

```bash
docker exec devcontainer-frappe-1 bash -lc \
  'curl -I -H "Host: sqlitepoc.localhost" http://127.0.0.1:8003/login'
```

Then fix/verify host mapping:

```bash
curl -I -H "Host: sqlitepoc.localhost" http://127.0.0.1:8103/login
```

If host mapping fails but container-local works, treat it as Docker networking, not Frappe.

### Phase 2: Commit Or Preserve Documentation

The planning docs are currently untracked in the Codex Frappe checkout:

```text
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc/docs/sqlite-only-runtime-poc-plan.md
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc/docs/sqlite-only-runtime-agent-handoff.md
```

Decide whether to:

- commit them on `poc/sqlite-only-runtime-plan`, or
- keep them as local handoff artifacts only.

### Phase 3: Implement Local Cache Backend

Patch target:

```text
frappe/utils/local_cache.py
frappe/__init__.py
frappe/utils/redis_wrapper.py
```

Config gate:

```json
{
  "cache_backend": "local"
}
```

Minimal API needed:

```text
make_key
set_value
get_value
delete_value
delete_key
delete_keys
get_keys
hset
hget
hgetall
hdel
exists
expire
setex
incrby
```

Implementation principle:

Use an in-process dict/local cache first. Do not introduce SQLite-backed cache until the minimal path works.

### Phase 4: Implement Sync Queue Backend

Patch target:

```text
frappe/utils/sync_jobs.py
frappe/utils/background_jobs.py
```

Config gate:

```json
{
  "queue_backend": "sync"
}
```

Behavior:

- `frappe.enqueue(...)` executes immediately.
- `enqueue_after_commit=True` registers the execution on `frappe.db.after_commit`.
- Direct calls to Redis/RQ-specific queue functions should fail clearly when sync backend is selected.

### Phase 5: Implement Realtime Noop Backend

Patch target:

```text
frappe/realtime.py
```

Config gate:

```json
{
  "realtime_backend": "noop"
}
```

Behavior:

- `publish_realtime` returns without Redis pubsub.
- `emit_via_redis` is guarded.
- `get_socketio_secret` does not require Redis in noop mode.

### Phase 6: Add SQLite Runner And Tests

Patch target:

```text
run_sqlite_frappe.py
frappe/tests/test_sqlite_only_runtime.py
SQLITE_ONLY_LIMITATIONS.md
```

Minimum test coverage:

- `frappe.db.db_type == "sqlite"`
- Administrator lookup.
- local cache set/get/delete.
- sync queue does not require Redis.
- realtime noop does not require Redis.
- ToDo insert/update/reload/delete.
- Single DocType read/write.

### Phase 7: Create Actual SQLite Site

Once patches exist, create a separate SQLite site/bench path rather than changing the MariaDB control site.

Target site name suggestion:

```text
sqliteonly.localhost
```

Expected config:

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

Validate without Redis/MariaDB only after the patched code passes with services still available.

## Kimi Usage Notes

Kimi was used for:

- planning the patch sequence,
- reading the existing SQLite POC plan,
- preparing this handoff outline.

Kimi may stall after reads. If it does, do not wait indefinitely. Use it for bounded file inspection or implementation steps, then verify directly with shell commands.

Useful Kimi prompt pattern:

```text
You are Kimi Worker under Codex supervision.
Do exactly one scoped task.
Do not commit.
Do not push.
Do not run destructive commands.
Report files changed, commands run, and risks.
```

## Immediate Resume Checklist

Run these first:

```bash
cd /Users/safwan/Code/docker/fdocker
docker ps --format '{{.ID}} {{.Names}} {{.Image}} {{.Status}}'
docker exec devcontainer-frappe-1 bash -lc 'cd /workspace/development/sqlitepoc && bench --site sqlitepoc.localhost list-apps'
docker exec devcontainer-frappe-1 bash -lc 'cd /workspace/development/sqlitepoc && git -C apps/frappe status --short --branch'
```

Expected:

```text
devcontainer-frappe-1, devcontainer-mariadb-1, devcontainer-redis-cache-1, devcontainer-redis-queue-1 running
frappe 16.20.0 poc/sqlite-only-runtime-plan
branch poc/sqlite-only-runtime-plan
```

Then choose the next phase deliberately.

## Completed POC Update - 2026-06-07

The first SQLite-only runtime POC has been implemented and validated.

### Files Patched

Host checkout:

```text
/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc
```

Patched files:

```text
frappe/__init__.py
frappe/utils/redis_wrapper.py
frappe/utils/background_jobs.py
frappe/realtime.py
frappe/locale.py
```

The same patched files were copied into the Docker bench app checkout:

```text
/workspace/development/sqlitepoc/apps/frappe
```

And into the reusable Docker source copy:

```text
/workspace/development/frappe-sqlite-source
```

### Patch Summary

`frappe/utils/redis_wrapper.py`

- Added `LocalCache`, a single-process in-memory implementation for the subset of `frappe.cache` used by boot, metadata, sessions, cache manager, rate helpers, and basic list/hash/set APIs.
- Added `LocalClientCache`, a single-process replacement for `frappe.client_cache`.

`frappe/__init__.py`

- Updated `setup_redis_cache_connection()` to use `LocalCache` and `LocalClientCache` when site config contains:

```json
{
  "cache_backend": "local"
}
```

`frappe/utils/background_jobs.py`

- Added `queue_backend = sync`.
- `frappe.enqueue(...)` executes immediately in-process.
- `enqueue_after_commit=True` registers the sync call on `frappe.db.after_commit`.
- Redis/RQ queue access fails clearly when sync queue backend is selected.

`frappe/realtime.py`

- Added `realtime_backend = noop`.
- `publish_realtime()` and `emit_via_redis()` return without Redis pubsub.
- `get_socketio_secret()` uses an in-process/site-config value rather than Redis when noop realtime is selected.

`frappe/locale.py`

- Fixed an uninitialized `value` local in `get_locale_value()`.
- This surfaced during ToDo update/version formatting when no language was available on the SQLite console session.

### SQLite Site Created

Site path:

```text
/Users/safwan/Code/docker/fdocker/development/sqlitepoc/sites/sqliteonly.localhost
```

Container path:

```text
/workspace/development/sqlitepoc/sites/sqliteonly.localhost
```

Creation command:

```bash
cd /workspace/development/sqlitepoc
bench new-site sqliteonly.localhost --db-type sqlite --admin-password admin --verbose
```

Result:

- SQLite warning shown by Frappe because upstream support is experimental.
- Database imported from `frappe/database/sqlite/framework_sqlite.db`.
- Frappe installed successfully.

Site config:

```json
{
  "cache_backend": "local",
  "db_name": "_629808a2a7925e7e",
  "db_password": "W15cKApUJOCL6dCj",
  "db_type": "sqlite",
  "disable_async": 1,
  "pause_scheduler": 1,
  "queue_backend": "sync",
  "realtime_backend": "noop"
}
```

### Tests Passed

Syntax:

```bash
python3 -m py_compile frappe/__init__.py frappe/utils/redis_wrapper.py frappe/utils/background_jobs.py frappe/realtime.py frappe/locale.py
```

SQLite smoke with services available:

- `frappe.db.db_type` returned `sqlite`.
- Administrator lookup returned `Administrator`.
- `frappe.cache.set_value()` / `get_value()` worked through `LocalCache`.
- `frappe.enqueue("frappe.get_site_config")` returned synchronously.
- `frappe.publish_realtime(...)` returned through noop realtime.
- ToDo insert worked.
- ToDo update/save worked after the `frappe/locale.py` fix.
- ToDo delete worked.

Migration:

```bash
bench --site sqliteonly.localhost migrate
```

Result:

- Migration completed successfully.
- DocType sync, fixtures, dashboards, customizations, languages, deferred inserts, orphan cleanup, portal menu, installed applications, and after-migrate hooks completed.
- Search index rebuild path did not fail under sync queue mode.

No-MariaDB/No-Redis proof:

Stopped:

```bash
docker stop devcontainer-mariadb-1 devcontainer-redis-cache-1 devcontainer-redis-queue-1
```

Then ran a SQLite site console smoke successfully:

- `db_type sqlite`
- Administrator lookup returned `Administrator`
- local cache returned `ok`
- sync enqueue returned `_dict`
- noop realtime returned `noop-ok`
- `frappe.db.count("ToDo")` returned `0`

Restarted services afterward:

```bash
docker start devcontainer-mariadb-1 devcontainer-redis-cache-1 devcontainer-redis-queue-1
```

HTTP check:

Started temporary server:

```bash
cd /workspace/development/sqlitepoc
bench serve --port 8004 --noreload
```

Checked login route:

```bash
curl -I -H "Host: sqliteonly.localhost" http://127.0.0.1:8004/login
```

Result:

```text
HTTP/1.1 200 OK
X-Page-Name: login
```

Temporary server was stopped with:

```bash
pkill -f 'bench serve --port 8004'
```

### Current Status

The minimal SQLite-only Frappe POC is working for:

- site creation,
- site migration,
- DB access through Frappe's document/ORM APIs,
- local in-process cache,
- synchronous queue execution,
- noop realtime,
- HTTP login page rendering,
- execution without MariaDB or Redis containers running.

This is a single-process local runtime POC. It is not a production-safe replacement for Redis/RQ/socket.io, and it does not claim full ERPNext/Frappe app coverage yet.

### Remaining Hardening Work

Recommended next agent tasks:

1. Add focused automated tests under `frappe/tests/test_sqlite_only_runtime.py` for local cache, sync queue, noop realtime, and ToDo CRUD.
2. Replace the broad `LocalCache` shim with a tighter protocol-backed interface if this is intended for upstream-quality code.
3. Audit cache API coverage against all `frappe.cache` calls and decide which Redis-only primitives should fail explicitly.
4. Add a dedicated `bench serve --sqlite-only` or local runner command that writes the needed site config automatically.
5. Run Desk login/browser validation, not just `/login` HTTP status.
6. Test an installed app beyond Frappe core and document which DocTypes or background hooks fail.
7. Decide whether `frappe/locale.py` fix should be separated as a general core bugfix.
