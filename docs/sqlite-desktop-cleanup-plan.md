# SQLite + Desktop Cleanup Plan

Date: 2026-06-08

## Objective

Move from the current working PoC to a clean Frappe-compatible++ repository shape:

- SQLite support remains inside normal Frappe runtime paths.
- SQLite is enabled only through site config or environment config.
- MariaDB/PostgreSQL remain the default and must keep working.
- Desktop lives as an optional root-level feature, similar to `docker/`.
- Future Frappe upstream syncs remain reviewable and manageable.

This is a later cleanup plan. Do not start this while the current desktop/runtime PoC is unstable.

## Desired Final Shape

Repository root should remain Frappe-shaped:

```text
frappe/
frappe.egg-info/
hooks.md
package.json
pyproject.toml
sider.yml
socketio.js
yarn.lock

desktop/
  shell/
  runtime/
  scripts/
  README.md

docker/
docs/
```

Desktop should be optional. It should behave like `docker/`: available to users who explicitly run a command, invisible to users who do not.

## Current State To Preserve

Working SQLite core:

- `db_type = sqlite`
- `cache_backend = local`
- `queue_backend = sync`
- `realtime_backend = noop`
- Frappe boots without MariaDB/Redis in the SQLite-only profile.
- Basic document CRUD, migrate, cache, sync enqueue, and no-op realtime have smoke coverage.

Working desktop:

- Tauri shell launches.
- PyInstaller sidecar starts.
- Frappe login route and assets load.
- First-run setup exists.
- Local site/data directory is used.
- Backup menu path exists.

## Phase 0: Freeze Current Working Evidence

Goal: make sure the known-good state is recoverable before cleanup.

Actions:

1. Tag or branch current working state.
2. Keep PR branch intact until cleanup branch is verified.
3. Record working app verification:
   - `/login` HTTP 200.
   - CSS/JS asset HTTP 200.
   - configured site folder created.
   - backup zip created.
   - no MariaDB/Redis needed for runtime.

Acceptance:

- Current app can still be rebuilt/launched from the pre-cleanup branch.
- Cleanup work happens on a new branch.

Suggested branch:

```bash
git switch -c cleanup/frappe-compatible-desktop-layout
```

## Phase 1: Move Desktop Under `desktop/`

Goal: isolate desktop files without changing behavior.

Current PoC paths:

```text
desktop_shell/
desktop_runtime/
scripts/sync-sidecar-into-app.sh
```

Target paths:

```text
desktop/shell/
desktop/runtime/
desktop/scripts/sync-sidecar-into-app.sh
desktop/README.md
```

Patch idea:

```bash
git mv desktop_shell desktop/shell
git mv desktop_runtime desktop/runtime
mkdir -p desktop/scripts
git mv scripts/sync-sidecar-into-app.sh desktop/scripts/sync-sidecar-into-app.sh
```

Then update references in:

- `desktop/shell/src-tauri/tauri.conf.json`
- `desktop/shell/src-tauri/Cargo.toml`
- `desktop/shell/src-tauri/src/lib.rs`
- `desktop/shell/package.json`
- `desktop/scripts/sync-sidecar-into-app.sh`
- root `README.md`
- `AGENTS.md`
- any docs that reference old paths.

Acceptance:

```bash
cd desktop/shell
npm run build
npm run tauri build
../scripts/sync-sidecar-into-app.sh
```

Then launch and verify `/login` and assets.

## Phase 2: Separate Root README From Desktop README

Goal: keep the root README suitable for the Frappe-compatible++ repo, not only desktop.

Root `README.md` should say:

- this is a Frappe-compatible fork with optional SQLite support,
- MariaDB/PostgreSQL remain default,
- SQLite is opt-in,
- desktop is optional under `desktop/`.

Move desktop-specific build/run details to:

```text
desktop/README.md
```

Acceptance:

- Root README does not read like a desktop-only project.
- Desktop instructions remain available and accurate.

## Phase 3: Define User Commands

Goal: make desktop usable either through explicit scripts or future bench commands.

Script path first:

```text
desktop/scripts/init.sh
desktop/scripts/build.sh
desktop/scripts/run.sh
desktop/scripts/package.sh
desktop/scripts/sync-sidecar-into-app.sh
```

Minimum script contract:

- `init.sh`: install desktop shell/runtime prerequisites.
- `build.sh`: build frontend, sidecar, and Tauri app.
- `run.sh`: launch the desktop app.
- `package.sh`: produce release bundle later.
- `sync-sidecar-into-app.sh`: copy sidecar internals into the `.app` after Tauri build.

Bench command can come later as a wrapper:

```bash
bench setup desktop
bench build-desktop
bench run-desktop
```

Patch idea for bench integration later:

- add commands under existing Frappe command modules only if they are optional,
- command should shell out to `desktop/scripts/*`,
- command must no-op/fail cleanly when desktop dependencies are missing.

Acceptance:

- `./desktop/scripts/run.sh` works from repo root.
- No normal Frappe/bench flow requires desktop dependencies.

## Phase 4: Clean Generated And Local Files

Goal: keep the repo source-only and sync-friendly.

Add or update ignore rules for generated/local artifacts:

```text
desktop/shell/node_modules/
desktop/shell/dist/
desktop/shell/src-tauri/target/
desktop/shell/src-tauri/gen/
desktop/shell/src-tauri/binaries/_internal/
build/
dist/
*.pyc
__pycache__/
scripts/sign-app.sh
```

Decision needed for sidecar binary:

Option A: keep tracked during PoC for easy testing.
Option B: move to Git LFS.
Option C: remove from Git and build/download as release artifact.

Recommended long term: Option C.

Acceptance:

- `git status --short` is clean after a normal build.
- local signing identity never enters Git.

## Phase 5: Keep SQLite Core In Frappe Runtime Paths

Goal: preserve compatibility with future upstream syncs.

Keep:

```text
frappe/database/sqlite/
frappe/search/sqlite_search.py
```

Keep shared-file changes small and config/capability gated:

- `frappe/database/__init__.py`
- `frappe/config.py`
- `frappe/installer.py`
- `frappe/__init__.py`
- `frappe/utils/background_jobs.py`
- `frappe/utils/redis_wrapper.py`
- `frappe/realtime.py`
- `frappe/model/document.py`
- `frappe/cache_manager.py`

Refactor target:

- avoid large `if sqlite` blocks in unrelated logic,
- prefer DB capability helpers where possible,
- keep `LocalCache`/`LocalClientCache` isolated,
- keep `queue_backend = sync` and `realtime_backend = noop` generic, not desktop-specific.

Acceptance:

- MariaDB site still works.
- SQLite site still works.
- The delta against upstream Frappe is mostly adapter files plus small config-gated hooks.

## Phase 6: Update Trackers After Cleanup

Goal: docs remain useful until they are moved to a separate repo.

Update:

- `docs/sqlite-upstream-sync-watchlist.md`
- `docs/sqlite-full-coverage-tracker.md`
- `docs/SQLITE_ONLY_LIMITATIONS.md`
- `docs/sqlite-production-readiness.md`

Record:

- new desktop paths,
- scripts/commands,
- latest verification,
- remaining gaps.

Later release cleanup:

- move heavy agent/research docs to a separate docs/research repo,
- keep only concise user-facing docs in this repo.

## Phase 7: Verification Matrix

Run this before merging cleanup.

Core SQLite:

```bash
bench new-site sqlite-cleanup.localhost --db-type sqlite --admin-password admin --force
bench --site sqlite-cleanup.localhost migrate
bench --site sqlite-cleanup.localhost run-tests --module frappe.tests.test_sqlite_only_runtime
```

Core non-SQLite guard:

```bash
bench new-site mariadb-guard.localhost --admin-password admin --mariadb-root-password 123 --force
bench --site mariadb-guard.localhost migrate
```

Desktop:

```bash
./desktop/scripts/init.sh
./desktop/scripts/build.sh
./desktop/scripts/run.sh
```

Browser/runtime:

- `GET /login` returns 200.
- compiled CSS/JS assets return 200.
- first-run setup screen appears on clean config.
- configured site boots after setup.
- backup action creates a zip.
- no MariaDB/Redis process is required for SQLite-only desktop runtime.

## Suggested Commit Sequence

1. `Move desktop PoC under desktop directory`
2. `Split desktop instructions from root README`
3. `Add desktop init build run scripts`
4. `Ignore desktop generated artifacts`
5. `Document Frappe-compatible SQLite desktop layout`
6. `Verify SQLite and desktop cleanup flow`

Keep each commit small. If a path move breaks the app, fix that before touching SQLite core.
