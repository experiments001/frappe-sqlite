# Release Cleanup TODO

Date: 2026-06-08

## Purpose

Track cleanup required before this repository can be treated as a clean Frappe-compatible++ distribution with optional SQLite and optional desktop packaging.

The current PoC proves two things:

- Frappe can run in a SQLite-only local profile.
- A macOS Tauri desktop shell can launch a PyInstaller sidecar and serve Frappe locally.

Before release, the generated desktop artifacts and source tree need a cleaner contract.

## Mental Model

Treat the desktop sidecar like a Vite/React build output:

```text
Source of truth:
frappe/
desktop runtime source
desktop shell source

Generated sidecar:
PyInstaller binary
PyInstaller _internal runtime

Generated app:
Tauri .app bundle
DMG or zip release package
```

The desktop app does not run directly from `frappe/`. It runs the PyInstaller sidecar. Therefore, changes in `frappe/database/sqlite/*` are not present in the desktop app until the sidecar and app bundle are rebuilt.

## Source Of Truth

Keep these in Git:

```text
frappe/
desktop/
  shell/
  runtime/
  scripts/
pyproject.toml
package.json
yarn.lock
```

Current PoC paths that should later move:

```text
desktop_shell/      -> desktop/shell/
desktop_runtime/    -> desktop/runtime/
scripts/sync-sidecar-into-app.sh -> desktop/scripts/sync-sidecar-into-app.sh
```

## Generated Artifacts

These should not be source of truth:

```text
desktop/shell/dist/
desktop/shell/src-tauri/target/
desktop/shell/src-tauri/gen/
desktop/shell/src-tauri/binaries/_internal/
dist/
build/
*.app
*.dmg
*.zip
__pycache__/
*.pyc
```

Decision still needed:

```text
desktop/shell/src-tauri/binaries/frappe-sqlite-aarch64-apple-darwin
```

For PoC, the sidecar binary may remain committed for convenience. For release, prefer one of:

- build from source during release,
- download from GitHub release artifacts,
- store with Git LFS if absolutely needed.

## P0 Before Release

- [ ] Move desktop code under root `desktop/`.
- [ ] Split root README from desktop README.
- [ ] Add ignore rules for generated desktop/runtime artifacts.
- [ ] Stop committing `_internal` runtime output.
- [ ] Decide whether the sidecar binary is tracked, Git LFS, or release-only.
- [ ] Add one command/script to rebuild sidecar from current source.
- [ ] Add one command/script to sync sidecar into Tauri app.
- [ ] Add one command/script to verify bundle freshness.
- [ ] Verify desktop sidecar contains latest SQLite performance/correctness fixes.
- [ ] Verify final `.app` contains the same SQLite files as source or an expected frozen copy.
- [ ] Preserve MariaDB/PostgreSQL default behavior.
- [ ] Preserve SQLite as opt-in via site config/environment.

## Missing Scripts

Target scripts:

```text
desktop/scripts/init.sh
desktop/scripts/build-sidecar.sh
desktop/scripts/sync-sidecar.sh
desktop/scripts/build-app.sh
desktop/scripts/run-dev.sh
desktop/scripts/run-packaged.sh
desktop/scripts/verify-bundle.sh
desktop/scripts/package.sh
```

Minimum contracts:

| Script | Purpose |
| --- | --- |
| `init.sh` | Install/check desktop prerequisites. |
| `build-sidecar.sh` | Build PyInstaller sidecar from the current Frappe source tree. |
| `sync-sidecar.sh` | Copy sidecar binary and `_internal` runtime into the Tauri expected locations. |
| `build-app.sh` | Build Vite/Tauri app bundle. |
| `run-dev.sh` | Run desktop against source/runtime dev mode when possible. |
| `run-packaged.sh` | Run the generated `.app` bundle. |
| `verify-bundle.sh` | Prove sidecar/app contains the intended SQLite code. |
| `package.sh` | Produce release package later. |

## Development Mode

Desired development modes:

### Source Runtime Mode

Use this for SQLite/Frappe work.

```text
Tauri shell -> local Python runner from source checkout -> Frappe source tree
```

Benefits:

- edits to `frappe/database/sqlite/*` take effect after server restart,
- no PyInstaller rebuild for every framework change,
- fastest inner loop.

TODO:

- [ ] Add `desktop/scripts/run-dev.sh`.
- [ ] Let Tauri point to a source-runner process or already-running local server.
- [ ] Document ports and config file locations.

### Packaged Runtime Mode

Use this for release confidence.

```text
Tauri shell -> PyInstaller sidecar -> frozen/copied Frappe runtime
```

Benefits:

- matches what users run,
- catches missing package metadata, assets, and PyInstaller hidden imports,
- verifies macOS app bundle behavior.

TODO:

- [ ] Add `desktop/scripts/build-sidecar.sh`.
- [ ] Add `desktop/scripts/build-app.sh`.
- [ ] Add `desktop/scripts/verify-bundle.sh`.

## Production Mode

Production users should run only generated app artifacts:

```text
frappe-sqlite-desktop.app
or
release DMG/zip
```

Production must not require:

- Docker,
- bench,
- MariaDB,
- Redis,
- source checkout,
- Python installed globally.

Production release flow should be:

```text
sync latest Frappe SQLite source
run SQLite tests
build sidecar
build app
verify bundle freshness
smoke-test app
sign/notarize
publish artifact
```

## Bundle Freshness Checks

The most important release guard is proving the frozen runtime is not stale.

Example checks:

```bash
shasum -a 256 frappe/database/sqlite/database.py
shasum -a 256 desktop/shell/src-tauri/binaries/_internal/frappe/database/sqlite/database.py
shasum -a 256 desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app/Contents/MacOS/_internal/frappe/database/sqlite/database.py
```

Also check for key SQLite fixes:

```bash
rg -n "BEGIN IMMEDIATE|_BUSY_TIMEOUT_MS|cache_size = -32768|mmap_size = 134217728|_NAMED_PARAM_RE|journal_mode = WAL" \
  frappe/database/sqlite/database.py \
  frappe/database/sqlite/setup_db.py \
  desktop/shell/src-tauri/binaries/_internal/frappe/database/sqlite/database.py \
  desktop/shell/src-tauri/binaries/_internal/frappe/database/sqlite/setup_db.py
```

The exact paths should be updated after `desktop_shell/` moves to `desktop/shell/`.

## SQLite Performance Fix Sync TODO

Current finding:

- checked-in Frappe source has the latest SQLite performance fixes,
- the existing desktop sidecar `_internal` runtime was built from older SQLite code,
- the final `.app` bundle therefore may run stale SQLite code.

Required now:

- [ ] Rebuild sidecar from the latest `experiments001/frappe-sqlite/main` source.
- [ ] Copy sidecar binary and `_internal` into Tauri binary/app locations.
- [ ] Rebuild or resync the `.app`.
- [ ] Verify markers in sidecar `_internal`.
- [ ] Verify markers in final `.app`.
- [ ] Run `/login` and asset smoke tests.

## Core Frappe Compatibility Watch

Keep these rules during all cleanup:

- SQLite must remain optional.
- MariaDB/PostgreSQL must remain default.
- Shared core changes should be small and config-gated.
- Desktop must consume SQLite support, not define it.
- Generated desktop artifacts must not be manually patched.

Related docs:

- `docs/sqlite-upstream-sync-watchlist.md`
- `docs/sqlite-desktop-cleanup-plan.md`
- `docs/sqlite-full-coverage-tracker.md`
- `docs/SQLITE_ONLY_LIMITATIONS.md`
