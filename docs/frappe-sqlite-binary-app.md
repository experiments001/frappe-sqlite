# Frappe + ERPNext SQLite — macOS Executable & Tauri Desktop App

## Overview

This document is the canonical plan for packaging the Frappe + ERPNext SQLite POC (running in the Docker devcontainer at `/Users/safwan/Code/docker/fdocker/development/`) into a distributable macOS desktop application — first as a standalone executable (Phase 1), then wrapped in a Tauri native shell (Phase 2).

**The code lives in Docker. The build artefacts are copied to the host Mac for testing and distribution.**

---

## Context

| Item | Value |
|---|---|
| Frappe bench (in Docker) | `/workspaces/frappe-bench` (inside `devcontainer-frappe-1`) |
| Docker compose root | `/Users/safwan/Code/docker/fdocker/.devcontainer` |
| Container name | `devcontainer-frappe-1` |
| POC repo | this repo |
| DB | SQLite (no MariaDB) |
| Queue | NOP stub (no Redis) |
| Realtime | NOP stub (no socket dependency) |
| Search | SQLite FTS |

---

## Hard Rules (never break these)

- Do NOT start with Phase 2 (Tauri) before Phase 1 is proven.
- Do NOT require end users to install Python, bench, MariaDB, Redis, Node, or developer tools.
- Do NOT bind server to `0.0.0.0`. Always `127.0.0.1`.
- Do NOT store writable DB/site files inside the app bundle or dist folder.
- Do NOT run migrations without first creating a timestamped backup.
- Do NOT attempt Windows or Linux packaging until macOS is proven.
- Do NOT use Electron.
- Do NOT rewrite Frappe logic in Rust — Tauri is shell only.

---

## Phases at a Glance

```
Phase 0  Verify bench works inside Docker
Phase 1  Python source runner (no bench serve)
Phase 2  PyInstaller --onedir on host Mac
Phase 3  Smoke test packaged binary
Phase 4  Tauri shell wrapping the Phase 2 binary
Phase 5  Signing, notarisation, DMG, updater
```

Phase 0–3 must be green before Phase 4 begins.

---

# Phase 0 — Verify Docker bench is working

**Goal:** Confirm the SQLite Frappe bench can serve ERPNext before touching any packaging.

**Who runs this:** You (on the host Mac), using `docker exec`.

## Step 0.1 — Connect to the container

```bash
docker exec -it devcontainer-frappe-1 bash
```

## Step 0.2 — Verify bench structure

Inside the container:

```bash
cd /workspaces/frappe-bench
ls apps        # expect: frappe  erpnext
ls sites       # expect: site1.local  assets  ...
```

## Step 0.3 — Confirm SQLite mode

```bash
cat sites/site1.local/site_config.json | python3 -m json.tool
```

Expected: `db_type: sqlite` or equivalent, no MariaDB host.

## Step 0.4 — Run bench serve

```bash
bench --site site1.local migrate
bench --site site1.local clear-cache
bench serve
```

Then from the host Mac, open `http://127.0.0.1:8000` (port must be forwarded in devcontainer config).

## Step 0.5 — Acceptance

- [ ] Login page loads at `http://127.0.0.1:8000`
- [ ] Can log in as Administrator
- [ ] Can create a Customer record
- [ ] No MariaDB process running
- [ ] No Redis process running

**Write the confirmed working command into `docs/STATUS.md` before continuing.**

---

# Phase 1 — Python source runner (no bench)

**Goal:** Replace `bench serve` with a Python script that starts Frappe's WSGI server directly, so we understand what `bench` does under the hood and can replicate it in a frozen binary.

**Where:** Inside the Docker container.

## Step 1.1 — Create the runtime directory structure

```bash
# inside container, at bench root /workspaces/frappe-bench
mkdir -p desktop_runtime/runner
mkdir -p desktop_runtime/scripts
mkdir -p desktop_runtime/pyinstaller/hooks
mkdir -p desktop_runtime/resources/seed_site/sites
```

## Step 1.2 — Create `runtime_paths.py`

File: `desktop_runtime/runner/runtime_paths.py`

```python
import os
import sys
from pathlib import Path

PRODUCT_NAME = "ERPNextSQLite"

def is_frozen() -> bool:
    return getattr(sys, "frozen", False)

def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    # desktop_runtime/runner/runtime_paths.py → bench root
    return Path(__file__).resolve().parents[2]

def app_data_root() -> Path:
    override = os.environ.get("ERPNEXT_SQLITE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "Library" / "Application Support" / PRODUCT_NAME

def sites_path() -> Path:
    return app_data_root() / "sites"

def logs_path() -> Path:
    return app_data_root() / "logs"

def ensure_base_dirs() -> None:
    app_data_root().mkdir(parents=True, exist_ok=True)
    sites_path().mkdir(parents=True, exist_ok=True)
    logs_path().mkdir(parents=True, exist_ok=True)
```

## Step 1.3 — Create `migration.py`

File: `desktop_runtime/runner/migration.py`

```python
import shutil
from pathlib import Path
from runtime_paths import bundle_root, sites_path, ensure_base_dirs

DEFAULT_SITE = "site1.local"

def seed_site_if_missing() -> None:
    ensure_base_dirs()
    target_site = sites_path() / DEFAULT_SITE
    if target_site.exists() and (target_site / "site_config.json").exists():
        return
    seed_root = bundle_root() / "resources" / "seed_site" / "sites"
    if not seed_root.exists():
        raise RuntimeError(f"Seed site not found: {seed_root}")
    source_site = seed_root / DEFAULT_SITE
    shutil.copytree(source_site, target_site, dirs_exist_ok=True)
    source_common = seed_root / "common_site_config.json"
    if source_common.exists():
        shutil.copy2(source_common, sites_path() / "common_site_config.json")

def run_migrations_if_needed() -> None:
    seed_site_if_missing()
    # Phase 1: seed only. Frappe programmatic migrate added in Phase 3.
```

## Step 1.4 — Create `server.py`

File: `desktop_runtime/runner/server.py`

```python
import os
import socket
import sys
from pathlib import Path
from werkzeug.serving import run_simple
from runtime_paths import bundle_root, sites_path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_SITE = "site1.local"

def find_free_port(start: int = 8765, end: int = 8865) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((DEFAULT_HOST, port)) != 0:
                return port
    raise RuntimeError("No free local port found")

def configure_python_paths() -> None:
    root = bundle_root()
    for p in [root / "apps" / "frappe", root / "apps" / "erpnext", root]:
        if p.exists():
            sys.path.insert(0, str(p))

def configure_frappe_env() -> None:
    os.environ.setdefault("FRAPPE_SITE_NAME", DEFAULT_SITE)
    os.environ.setdefault("SITES_PATH", str(sites_path()))
    os.environ.setdefault("FRAPPE_SITES_PATH", str(sites_path()))
    os.environ.setdefault("ERPNEXT_SQLITE_DESKTOP", "1")
    os.environ.setdefault("NO_REDIS", "1")
    os.environ.setdefault("NO_MARIADB", "1")

def serve(port: int | None = None) -> int:
    configure_python_paths()
    configure_frappe_env()
    selected_port = port or find_free_port()
    from frappe.app import application
    print(f"Starting ERPNext SQLite on http://{DEFAULT_HOST}:{selected_port}")
    print(f"Sites path: {sites_path()}")
    run_simple(
        hostname=DEFAULT_HOST,
        port=selected_port,
        application=application,
        use_reloader=False,
        use_debugger=False,
        threaded=True,
    )
    return selected_port
```

> **Note:** If `frappe.app.application` is not the correct import in this SQLite port, inspect `bench serve` to find the actual WSGI entry point and update this file. Document the correct import in `docs/STATUS.md`.

## Step 1.5 — Create `main.py`

File: `desktop_runtime/runner/main.py`

```python
import argparse
import threading
import time
import webbrowser
from migration import run_migrations_if_needed
from server import serve, DEFAULT_HOST, find_free_port

def main() -> None:
    parser = argparse.ArgumentParser(description="ERPNext SQLite Desktop Runtime")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--migrate-only", action="store_true")
    args = parser.parse_args()

    run_migrations_if_needed()

    if args.migrate_only:
        print("Migration check completed.")
        return

    port = args.port or find_free_port()
    url = f"http://{DEFAULT_HOST}:{port}"

    if not args.no_browser:
        def open_later():
            time.sleep(2)
            webbrowser.open(url)
        threading.Thread(target=open_later, daemon=True).start()

    serve(port=port)

if __name__ == "__main__":
    main()
```

## Step 1.6 — Test source runner in container

```bash
cd /workspaces/frappe-bench
python desktop_runtime/runner/main.py --port 8765 --no-browser
```

From host Mac: `http://127.0.0.1:8765` (ensure port is forwarded).

## Step 1.7 — Acceptance

- [ ] ERPNext loads without `bench serve`
- [ ] Login works
- [ ] Data reads/writes persist in SQLite
- [ ] No MariaDB, no Redis needed
- [ ] `ERPNEXT_SQLITE_DATA_DIR` override works

---

# Phase 2 — PyInstaller build on host Mac

**Goal:** Produce `dist/erpnext-sqlite-macos/erpnext-sqlite` — a standalone folder runnable without Python.

**The PyInstaller build runs on the host Mac**, not inside Docker, because the binary must target the host architecture (arm64/x86_64 macOS), not Linux.

## Step 2.1 — Export bench files from Docker to host

```bash
# On host Mac terminal
BENCH_ROOT=/Users/safwan/Code/docker/fdocker/development

docker cp devcontainer-frappe-1:/workspaces/frappe-bench/apps \
  $BENCH_ROOT/apps

docker cp devcontainer-frappe-1:/workspaces/frappe-bench/sites \
  $BENCH_ROOT/sites

docker cp devcontainer-frappe-1:/workspaces/frappe-bench/desktop_runtime \
  $BENCH_ROOT/desktop_runtime
```

> **Note:** `sites/` will include `site.db`. This becomes the seed for first launch. Verify the SQLite DB is complete before copying.

## Step 2.2 — Set up Python venv on host Mac

```bash
cd $BENCH_ROOT

python3 -m venv .venv-macos
source .venv-macos/bin/activate

# Install Frappe dependencies from apps/frappe
pip install -e apps/frappe --no-deps
pip install -e apps/erpnext --no-deps

# Install packaging tools
pip install pyinstaller werkzeug
```

> **Note:** If Frappe has many transitive dependencies, use `pip install -r apps/frappe/requirements.txt` first.

## Step 2.3 — Build frontend assets in Docker (not on host)

```bash
docker exec -it devcontainer-frappe-1 bash -c \
  "cd /workspaces/frappe-bench && bench build"

# Then re-copy assets to host
docker cp devcontainer-frappe-1:/workspaces/frappe-bench/sites/assets \
  $BENCH_ROOT/sites/assets
```

## Step 2.4 — Prepare seed site

```bash
cd $BENCH_ROOT

rm -rf desktop_runtime/resources/seed_site
mkdir -p desktop_runtime/resources/seed_site/sites

cp -R sites/site1.local desktop_runtime/resources/seed_site/sites/site1.local
[ -f sites/common_site_config.json ] && \
  cp sites/common_site_config.json \
     desktop_runtime/resources/seed_site/sites/common_site_config.json
```

## Step 2.5 — Create PyInstaller hooks

File: `desktop_runtime/pyinstaller/hooks/hook-frappe.py`

```python
from PyInstaller.utils.hooks import collect_all
datas, binaries, hiddenimports = collect_all("frappe")
```

File: `desktop_runtime/pyinstaller/hooks/hook-erpnext.py`

```python
from PyInstaller.utils.hooks import collect_all
datas, binaries, hiddenimports = collect_all("erpnext")
```

## Step 2.6 — Create PyInstaller spec

File: `desktop_runtime/pyinstaller/erpnext_sqlite.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path.cwd()

datas, binaries, hiddenimports = [], [], []

for package in ["frappe", "erpnext"]:
    pd, pb, ph = collect_all(package)
    datas += pd; binaries += pb; hiddenimports += ph

for src, dest in [
    ("apps/frappe", "apps/frappe"),
    ("apps/erpnext", "apps/erpnext"),
    ("sites/assets", "sites/assets"),
    ("desktop_runtime/resources", "resources"),
]:
    p = ROOT / src
    if p.exists():
        datas.append((str(p), dest))

hiddenimports += collect_submodules("frappe")
hiddenimports += collect_submodules("erpnext")

a = Analysis(
    ["desktop_runtime/runner/main.py"],
    pathex=[str(ROOT), str(ROOT/"apps"/"frappe"), str(ROOT/"apps"/"erpnext")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["desktop_runtime/pyinstaller/hooks"],
    excludes=["tkinter", "pytest", "IPython"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="erpnext-sqlite",
    debug=False, strip=False, upx=False, console=True,
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False,
    name="erpnext-sqlite-macos",
)
```

## Step 2.7 — Create the build script

File: `desktop_runtime/scripts/build_macos_pyinstaller.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."   # bench root

echo "=== Step 1: Build frontend assets in Docker ==="
docker exec devcontainer-frappe-1 bash -c \
  "cd /workspaces/frappe-bench && bench build"
docker cp devcontainer-frappe-1:/workspaces/frappe-bench/sites/assets ./sites/assets

echo "=== Step 2: Prepare seed site ==="
rm -rf desktop_runtime/resources/seed_site
mkdir -p desktop_runtime/resources/seed_site/sites
cp -R sites/site1.local desktop_runtime/resources/seed_site/sites/site1.local
[ -f sites/common_site_config.json ] && \
  cp sites/common_site_config.json \
     desktop_runtime/resources/seed_site/sites/common_site_config.json

echo "=== Step 3: PyInstaller ==="
source .venv-macos/bin/activate
rm -rf build dist
pyinstaller desktop_runtime/pyinstaller/erpnext_sqlite.spec --clean --noconfirm

echo ""
echo "Build complete → dist/erpnext-sqlite-macos/erpnext-sqlite"
```

Run from `$BENCH_ROOT`:

```bash
chmod +x desktop_runtime/scripts/build_macos_pyinstaller.sh
./desktop_runtime/scripts/build_macos_pyinstaller.sh
```

---

# Phase 3 — Smoke test

**Goal:** Verify the packaged binary works without a Python install.

File: `desktop_runtime/scripts/smoke_test_macos.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

APP="./dist/erpnext-sqlite-macos/erpnext-sqlite"
[ -x "$APP" ] || { echo "Executable not found: $APP"; exit 1; }

TEST_DIR="$(pwd)/tmp/test-data"
rm -rf "$TEST_DIR"; mkdir -p "$TEST_DIR"
mkdir -p tmp

echo "Starting app..."
ERPNEXT_SQLITE_DATA_DIR="$TEST_DIR" "$APP" --port 8765 --no-browser \
  > tmp/erpnext-sqlite.log 2>&1 &
PID=$!
echo "PID: $PID"

sleep 10

echo "Checking HTTP..."
curl -fsI http://127.0.0.1:8765 || {
  echo "FAILED — HTTP not up"
  cat tmp/erpnext-sqlite.log
  kill "$PID" || true; exit 1
}

echo "Checking no external DB/queue..."
pgrep -x mysqld >/dev/null && echo "WARNING: mysqld running — verify app isn't using it"
pgrep -x redis-server >/dev/null && echo "WARNING: redis-server running — verify app isn't using it"

kill "$PID" || true
echo "Smoke test PASSED."
```

```bash
chmod +x desktop_runtime/scripts/smoke_test_macos.sh
./desktop_runtime/scripts/smoke_test_macos.sh
```

## Phase 3 Acceptance Criteria

- [ ] Binary runs without Python installed on the test account
- [ ] No MariaDB required
- [ ] No Redis required
- [ ] HTTP response at `127.0.0.1:8765`
- [ ] ERPNext login page renders
- [ ] Can log in as Administrator
- [ ] Can create: Customer, Item, Sales Invoice
- [ ] Data persists after kill + restart
- [ ] SQLite DB at `~/Library/Application Support/ERPNextSQLite/sites/site1.local/`
- [ ] Dist folder contains no user-writable DB
- [ ] Zip + unzip + run works on a second macOS user account

## Phase 3 Debugging Checklist

```bash
# Missing imports
grep -E "ModuleNotFoundError|ImportError|No module named" tmp/erpnext-sqlite.log

# Fix: add to hiddenimports in spec
hiddenimports += ["missing.module"]
# or
hiddenimports += collect_submodules("missing_package")

# Missing templates/assets
# Fix: add to datas in spec
datas += [("apps/frappe/frappe/templates", "frappe/templates")]

# Port conflict
# Dynamic port already implemented in find_free_port()

# Site config missing
ls ~/Library/Application\ Support/ERPNextSQLite/sites/site1.local/
```

If PyInstaller becomes unworkable, fall back to Nuitka:

```bash
pip install nuitka ordered-set zstandard
python -m nuitka \
  --standalone \
  --output-dir=dist-nuitka \
  --output-filename=erpnext-sqlite \
  --include-package=frappe \
  --include-package=erpnext \
  --include-data-dir=sites/assets=sites/assets \
  --include-data-dir=desktop_runtime/resources=resources \
  desktop_runtime/runner/main.py
```

Do not switch to Nuitka before one honest PyInstaller attempt.

---

# Phase 4 — Tauri desktop shell

**Start only after Phase 3 acceptance criteria are all green.**

## Architecture

```
Tauri App (macOS .app / .dmg)
  ├─ Sidecar: erpnext-sqlite (Phase 2 binary)
  ├─ Sidecar starts, binds 127.0.0.1:<port>
  ├─ Tauri waits for healthcheck (poll HTTP HEAD)
  ├─ Tauri WebView loads http://127.0.0.1:<port>
  └─ User sees native window, no browser, no URL bar
```

Tauri does NOT contain any Frappe logic. It is only: window, sidecar lifecycle, native menu, updater.

## Step 4.1 — Create Tauri app

```bash
cd $BENCH_ROOT
mkdir desktop_shell && cd desktop_shell
npm create tauri-app@latest
# Choose: Vite + Vanilla TS or React, npm or pnpm
```

## Step 4.2 — Copy binary as sidecar

```bash
mkdir -p desktop_shell/src-tauri/binaries

cp dist/erpnext-sqlite-macos/erpnext-sqlite \
  desktop_shell/src-tauri/binaries/erpnext-sqlite-aarch64-apple-darwin
# For Intel: erpnext-sqlite-x86_64-apple-darwin
```

Add to `src-tauri/tauri.conf.json` under `bundle`:

```json
{
  "bundle": {
    "externalBin": ["binaries/erpnext-sqlite"]
  }
}
```

## Step 4.3 — Shell plugin permissions

```bash
cd desktop_shell
npm run tauri add shell
```

`src-tauri/capabilities/default.json`:

```json
{
  "identifier": "default",
  "windows": ["main"],
  "permissions": [
    "shell:default",
    {
      "identifier": "shell:allow-execute",
      "allow": [{ "name": "erpnext-sqlite", "sidecar": true }]
    }
  ]
}
```

## Step 4.4 — Frontend sidecar launcher

`desktop_shell/src/main.ts`:

```typescript
import { Command } from "@tauri-apps/plugin-shell";

const PORT = 8765;
const URL = `http://127.0.0.1:${PORT}`;

async function sleep(ms: number) {
  return new Promise(r => setTimeout(r, ms));
}

async function waitForServer(attempts = 60) {
  for (let i = 0; i < attempts; i++) {
    try {
      const r = await fetch(URL, { method: "HEAD" });
      if (r.ok || r.status < 500) return;
    } catch (_) {}
    await sleep(1000);
  }
  throw new Error("Backend did not start within 60s");
}

async function start() {
  const cmd = Command.sidecar("binaries/erpnext-sqlite", [
    "--port", String(PORT), "--no-browser",
  ]);
  cmd.stdout.on("data", l => console.log("[backend]", l));
  cmd.stderr.on("data", l => console.error("[backend]", l));
  await cmd.spawn();
  await waitForServer();
  window.location.href = URL;
}

start().catch(err => {
  document.body.innerHTML = `<h2>Failed to start ERPNext</h2><pre>${err}</pre>`;
});
```

## Step 4.5 — Build macOS app

```bash
cd desktop_shell
npm install
npm run tauri build
```

Expected output:

```
src-tauri/target/release/bundle/macos/ERPNext SQLite.app
src-tauri/target/release/bundle/dmg/ERPNext SQLite_*.dmg
```

## Step 4.6 — Phase 4 Acceptance Criteria

- [ ] Native window opens (no browser launches)
- [ ] Backend starts automatically
- [ ] ERPNext login loads inside WebView
- [ ] Data persists after app restart
- [ ] App closes → backend process terminates
- [ ] App only binds 127.0.0.1
- [ ] .app can be moved to `/Applications` and works

---

# Phase 5 — Signing, Notarisation, Updater (post-MVP)

These steps are deferred until Phase 4 is stable.

## Signing

```bash
codesign --deep --force --options runtime \
  --sign "Developer ID Application: <Team>" \
  dist/erpnext-sqlite-macos/erpnext-sqlite

# Tauri handles signing the .app wrapper via tauri.conf.json
```

## Notarisation

```bash
xcrun notarytool submit ERPNextSQLite.dmg \
  --apple-id <email> --team-id <team> --password <app-specific> --wait
```

## Updater plan (tauri-plugin-updater)

```
Storage:       Cloudflare R2 or S3
Update source: latest.json (signed)
Artefacts:     ERPNextSQLite_<ver>_aarch64.dmg + ERPNextSQLite_<ver>_x64.dmg

Update flow:
  1. App starts
  2. Check latest.json
  3. If newer: download signed DMG, install, restart
  4. On first launch after update: backup SQLite DB, run migrations

Backup location:
  ~/Library/Application Support/ERPNextSQLite/backups/
    pre-update-<old-ver>-<timestamp>.sqlite
```

---

# Repository Structure After All Phases

```
frappe-core-sqlite-poc/  (or bench root)
  apps/
    frappe/
    erpnext/
  sites/
    site1.local/
    assets/
  desktop_runtime/
    README.md
    runner/
      main.py
      runtime_paths.py
      server.py
      migration.py
    scripts/
      build_macos_pyinstaller.sh
      smoke_test_macos.sh
    pyinstaller/
      erpnext_sqlite.spec
      hooks/
        hook-frappe.py
        hook-erpnext.py
    resources/
      seed_site/
        sites/
          common_site_config.json
          site1.local/
  desktop_shell/           ← Phase 4
    package.json
    src/
      main.ts
    src-tauri/
      tauri.conf.json
      binaries/
        erpnext-sqlite-aarch64-apple-darwin
      src/
        main.rs
  docs/
    frappe-sqlite-binary-app.md   ← this file
    STATUS.md                     ← live progress log
    sqlite-production-readiness.md
  dist/                    ← gitignored
    erpnext-sqlite-macos/
```

---

# Implementation Order (Strict)

```
[ ] 0.1  Verify bench serve works in Docker (Phase 0)
[ ] 0.2  Document working command in docs/STATUS.md
[ ] 1.1  Create desktop_runtime/runner/ files in Docker
[ ] 1.2  Test python main.py --port 8765 in Docker
[ ] 1.3  Confirm ERPNext loads via Python runner, not bench
[ ] 2.1  Copy bench files from Docker to host Mac
[ ] 2.2  Set up Python venv on host Mac
[ ] 2.3  Install Frappe deps in host venv
[ ] 2.4  Build frontend assets in Docker, copy to host
[ ] 2.5  Prepare seed site on host
[ ] 2.6  Create PyInstaller spec + hooks
[ ] 2.7  Run build_macos_pyinstaller.sh on host
[ ] 3.1  Run smoke_test_macos.sh
[ ] 3.2  Manual login + CRUD test
[ ] 3.3  Restart persistence test
[ ] 3.4  Test on second macOS user account (no Python installed)
[ ] 4.1  Create Tauri app scaffold
[ ] 4.2  Copy Phase 2 binary as Tauri sidecar
[ ] 4.3  Wire sidecar launch in frontend
[ ] 4.4  Build .app and .dmg
[ ] 4.5  End-to-end Tauri acceptance test
[ ] 5.1  Code signing (deferred)
[ ] 5.2  Notarisation (deferred)
[ ] 5.3  Auto-updater (deferred)
```

---

# Multi-Agent Coordination Protocol

This section defines how multiple agents (Claude, Kimi, Codex, or any future worker) can work on this project in parallel without stepping on each other.

## Shared Context Files

All agents read and write these files. These are the source of truth, not chat history.

| File | Purpose |
|---|---|
| `docs/STATUS.md` | Current phase, what works, what's broken, last verified command |
| `docs/PROGRESS.md` | Granular per-step completion log with timestamps |
| `docs/BLOCKERS.md` | Open blockers — one section per issue, with owner and status |
| `docs/DECISIONS.md` | Architecture decisions made and rationale |

## STATUS.md Format

```markdown
# STATUS

Last updated: 2026-06-07 by Claude

## Current Phase
Phase 1 — Python source runner

## Working
- bench serve works in Docker at http://127.0.0.1:8000
- Verified: SQLite, no MariaDB, no Redis

## Broken / Unknown
- frappe.app.application import path not yet confirmed in SQLite port

## Next Action
[ Agent: Claude ] Run `python desktop_runtime/runner/main.py --port 8765` in container
```

## PROGRESS.md Format

Each entry is a single line, never deleted, only appended:

```markdown
# PROGRESS LOG

2026-06-07T10:00Z [Claude]  Phase 0.1 DONE — bench serve confirmed working
2026-06-07T10:15Z [Claude]  Phase 0.2 DONE — STATUS.md updated with working command
2026-06-07T11:00Z [Kimi]    Phase 1.1 DONE — desktop_runtime/runner/ files created in Docker
2026-06-07T11:30Z [Kimi]    Phase 1.2 BLOCKED — frappe.app.application import fails, see BLOCKERS.md
2026-06-07T12:00Z [Claude]  Phase 1.2 DONE — fixed import, correct entry is frappe.app:application
```

## BLOCKERS.md Format

```markdown
# BLOCKERS

## OPEN: frappe.app import path

**Opened:** 2026-06-07T11:30Z by Kimi
**Owner:** Claude
**Status:** Investigating

frappe.app.application fails with ImportError in SQLite port.
Need to inspect actual bench serve implementation to find correct WSGI callable.

**Resolution:** (leave blank until fixed)

---

## CLOSED: site config missing on first launch

**Opened:** 2026-06-07T14:00Z by Kimi
**Closed:** 2026-06-07T14:45Z by Claude
**Fix:** seed_site_if_missing() was not copying common_site_config.json — fixed in migration.py
```

## Agent Work Allocation

Each agent claims a step by writing to PROGRESS.md before starting:

```markdown
2026-06-07T10:00Z [Claude]  Phase 1.1 STARTED — creating runner files
```

This prevents two agents working on the same step simultaneously.

If a step takes more than 30 minutes without a progress update, it is considered stalled and another agent may pick it up — but must write a STARTED line first.

## Agent Handoff Protocol

When finishing a step, an agent must:

1. Append a DONE line to `PROGRESS.md`
2. Update `STATUS.md` with current state
3. If blocked, add entry to `BLOCKERS.md`
4. Commit all changes with message: `progress: Phase <N>.<M> <description>`

## Git Commit Convention

```
progress: Phase 0.1 bench serve verified in Docker
progress: Phase 1.2 Python runner starts Frappe WSGI
fix: Phase 1.2 correct frappe.app import path
progress: Phase 2.7 PyInstaller build successful
blocker: Phase 3.1 smoke test fails - missing jinja2 template
fix: Phase 3.1 add jinja2 to PyInstaller hiddenimports
```

## Parallel Work Rules

Phases must be done in order. Within a phase, steps must be done in order.

Exception: docs and scripts (non-runtime files) may be prepared ahead of their phase as long as they are clearly marked `[DRAFT — not yet tested]`.

An agent must NOT modify files owned by another agent's in-progress step without first writing a note in BLOCKERS.md and waiting for acknowledgement.

## Quick Orientation for a New Agent

If you are a new agent joining this project, do this first:

```bash
cat docs/STATUS.md      # where we are
cat docs/PROGRESS.md    # what has been done
cat docs/BLOCKERS.md    # what is broken
cat docs/DECISIONS.md   # why things are the way they are
```

Then claim your next unclaimed step in PROGRESS.md before starting any work.

---

# Success Definition

The project is complete when a non-developer user can:

1. Download the app (zip or dmg)
2. Open it
3. Use ERPNext (create invoices, customers, items)
4. Close and reopen — previous data is there
5. Never install Frappe, bench, MariaDB, Redis, Python, or Node
6. Never see a terminal, URL bar, or developer tool
