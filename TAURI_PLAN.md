# Tauri Phase 4 — Master Plan

## Goal
Wrap the PyInstaller binary (`dist/frappe-sqlite-macos/frappe-sqlite`) in a Tauri native macOS app with an in-app WebView. No external browser needed.

## Directory
`/Users/safwan/Code/docker/fdocker/development/frappe-sqlite-tauri/`

## Architecture
```
Tauri App
  ├─ Sidecar: frappe-sqlite-aarch64-apple-darwin (copied from dist/)
  ├─ Sidecar starts, binds 127.0.0.1:<port>
  ├─ Tauri waits for healthcheck (poll HTTP HEAD)
  ├─ Tauri WebView loads http://127.0.0.1:<port>
  └─ User sees native window, no browser, no URL bar
```

## Agent Assignments

### Agent A: Tauri Scaffold & Infrastructure (DEPENDENCY: none)
**Scope:**
1. Create Tauri app scaffold in `desktop_shell/`
   - Use `npm create tauri-app@latest` with Vite + Vanilla TS
   - Project name: `frappe-sqlite-desktop`
   - Window title: "Frappe SQLite"
2. Copy sidecar binary
   - From: `dist/frappe-sqlite-macos/frappe-sqlite`
   - To: `desktop_shell/src-tauri/binaries/frappe-sqlite-aarch64-apple-darwin`
3. Configure `tauri.conf.json`
   - Add `"externalBin": ["binaries/frappe-sqlite"]` under `bundle`
   - Set window size to 1400x900
   - Set fullscreen to false
   - Set resizable to true
4. Add shell plugin permissions
   - `npm run tauri add shell`
   - Update `src-tauri/capabilities/default.json`
5. Commit: `progress: Phase 4.1-4.3 Tauri scaffold, sidecar, permissions`

**Output files:**
- `desktop_shell/package.json`
- `desktop_shell/src-tauri/tauri.conf.json`
- `desktop_shell/src-tauri/capabilities/default.json`
- `desktop_shell/src-tauri/binaries/frappe-sqlite-aarch64-apple-darwin`

### Agent B: Frontend Launcher & Healthcheck (DEPENDENCY: Agent A DONE)
**Scope:**
1. Write `desktop_shell/src/main.ts`
   - Import `Command` from `@tauri-apps/plugin-shell`
   - Start sidecar with `--port 8765 --no-browser`
   - Poll HTTP HEAD on `http://127.0.0.1:8765` for up to 60s
   - On success: navigate WebView to the URL
   - On failure: show error page in WebView
2. Update `desktop_shell/index.html` with a loading spinner
3. Style the error page
4. Commit: `progress: Phase 4.4 frontend sidecar launcher`

**Output files:**
- `desktop_shell/src/main.ts`
- `desktop_shell/index.html`
- `desktop_shell/src/style.css`

### Agent C: Build, Test & Fix (DEPENDENCY: Agent B DONE)
**Scope:**
1. Run `npm install` in `desktop_shell/`
2. Run `npm run tauri build`
3. Test the built `.app`:
   - Double-click opens native window
   - Backend starts automatically
   - ERPNext login loads inside WebView
   - Login works
   - Data persists after app restart
4. Fix any build/runtime issues
5. Write `desktop_shell/README.md` with build instructions
6. Commit: `progress: Phase 4.5 Tauri build and test complete`

**Output:**
- `src-tauri/target/release/bundle/macos/Frappe SQLite.app`
- `src-tauri/target/release/bundle/dmg/Frappe SQLite_*.dmg`

## Coordination Protocol
1. Each agent reads `TAURI_PLAN.md` and `PROGRESS.md` before starting
2. Each agent appends to `PROGRESS.md` with STARTED/DONE timestamps
3. Each agent updates `STATUS.md` on completion
4. Each agent commits with message: `progress: Phase 4.X <description>`
5. If blocked, add to `BLOCKERS.md`

## Shared Context Files
| File | Purpose |
|---|---|
| `TAURI_PLAN.md` | This file — master plan |
| `STATUS.md` | Current state |
| `PROGRESS.md` | Timestamped completion log |
| `BLOCKERS.md` | Open issues |
