# AGENTS.md

This project is a Frappe-compatible fork with optional SQLite support and optional host-native macOS desktop packaging. Read this file before making changes.

## Core Intent

SQLite support must stay inside normal Frappe runtime paths and remain opt-in through site config/environment config. The desktop app must run on the host Mac, outside Docker.

Runtime target:

- Tauri shell on macOS
- PyInstaller Python sidecar on macOS
- SQLite site/data under `~/Library/Application Support/FrappeSQLite/`
- No MariaDB
- No Redis
- No Docker
- No bench process required at app runtime

Docker may be used only as historical/reference validation for the separate SQLite bench POC. Do not make the desktop app depend on Docker.

## Important Paths

- Project root: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri`
- SQLite backend: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/frappe/database/sqlite`
- Desktop root: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop`
- Tauri shell: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop/shell`
- Tauri Rust/backend config: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop/shell/src-tauri`
- Python desktop runtime: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop/runtime`
- Desktop scripts: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop/scripts`
- Built app: `/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app`
- Historical PyInstaller build checkout: `/Users/safwan/Code/docker/fdocker/development/sqlitepoc`

## Do Not Do These Things

Do not remove `.dist-info`, `.egg-info`, `METADATA`, `RECORD`, or package metadata directories from PyInstaller `_internal`.

These are runtime data. Python packages use them through `importlib.metadata`, package resource lookup, plugin discovery, entry points, and version checks. Removing them can cause failures such as:

```text
ModuleNotFoundError: No module named 'pkg_resources'
PackageNotFoundError
```

Do not make code signing pass by deleting Python metadata. If `codesign` fails, capture the exact failing file/error and fix that specific signing issue.

Do not change the desktop app to call Docker, `bench serve`, MariaDB, Redis, Supervisor, or a container-only path.

Do not assume the Docker SQLite POC URL is the desktop runtime. The desktop runtime should serve from the PyInstaller sidecar on host localhost, normally `127.0.0.1:8765`.

Do not remove the `socket.getfqdn` workaround in `desktop/runtime/runner/server.py` unless you have reproduced and fixed the macOS `.app` sidecar startup hang another way.

Do not commit, push, delete files, or run destructive cleanup unless explicitly instructed.

Do not touch secrets, signing identities, keychains, provisioning profiles, or user credentials without explicit permission.

## Known Packaging Issue

After signing/package cleanup, the app may fail with:

```text
ModuleNotFoundError: No module named 'pkg_resources'
```

Current diagnosis:

- Raw PyInstaller output has `semantic_version-2.10.0.dist-info`.
- The current signed `.app` bundle may not have that metadata under `Contents/MacOS/_internal`.
- The `.app` bundle may also lack `pkg_resources`.
- This points to the app-bundle copy/signing cleanup step, not SQLite itself.

Primary fix:

1. Preserve all PyInstaller `_internal/*.dist-info` and related metadata in the `.app` bundle.
2. Add defensive PyInstaller spec entries for `semantic_version`, `setuptools`, and `pkg_resources`.
3. Rebuild the sidecar/app.
4. Sign Mach-O binaries and the app without deleting metadata.
5. Test sidecar and GUI launch on the host Mac.

Patch idea for the PyInstaller spec, currently in the historical `sqlitepoc` build checkout:

```python
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

# later, after datas/hiddenimports are initialized
datas += copy_metadata("semantic_version")
datas += copy_metadata("setuptools")

hiddenimports += [
    "pkg_resources",
    "setuptools",
    "semantic_version",
]
```

## Required Verification

After any packaging/signing change, run host-native tests.

Check raw dist metadata:

```bash
find /Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/dist/frappe-sqlite-macos/_internal -maxdepth 1 -name '*semantic*' -print
```

Check app bundle metadata:

```bash
APP=/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app
find "$APP/Contents/MacOS/_internal" -maxdepth 1 -name '*semantic*' -print
find "$APP/Contents/MacOS/_internal" -maxdepth 2 -path '*pkg_resources*' -print
```

Run sidecar directly:

```bash
APP=/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app
"$APP/Contents/MacOS/frappe-sqlite" --port 8766 --no-browser
```

In another shell:

```bash
curl -I http://127.0.0.1:8766/login
```

Expected:

```text
HTTP/1.1 200 OK
```

Run Tauri E2E:

```bash
cd /Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri
./desktop/scripts/verify-bundle.sh
```

Expected:

```text
Bundle freshness verified.
```

This freshness check does not replace the host browser smoke test. Also run the sidecar directly and verify `/login` plus CSS/JS assets.

Launch app:

```bash
open /Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/desktop/shell/src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app
```

Manual checks:

- Window opens.
- Sidecar listens on `127.0.0.1:8765`.
- Login page loads.
- Administrator login works with password `admin` if using the seeded POC site.
- Basic create/update/delete works.
- Data persists after quit and relaunch.

## Reference Docs

- Current handoff: `/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/docs/tauri-desktop-sqlite-handoff.md`
- SQLite POC handoff: `/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc/docs/sqlite-only-runtime-agent-handoff.md`
- Coverage tracker: `/Users/safwan/Documents/Codex/2026-06-06/https-github-com-lubusin-frappe-playground/frappe-core-sqlite-poc/docs/sqlite-full-coverage-tracker.md`

## Agent Operating Rules

Before editing, read this file and inspect the current app bundle contents.

Prefer small scoped changes. Preserve the working SQLite runtime behavior. If a fix requires changing packaging and runtime code at the same time, document why.

When reporting back, include:

- Files changed
- Commands run
- Test results
- Whether the app was tested outside Docker
- Remaining risks
