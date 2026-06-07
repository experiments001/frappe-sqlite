# Frappe SQLite Desktop

A native macOS desktop app that bundles the Frappe SQLite backend and serves it in an embedded Tauri WebView. No external browser needed.

## Prerequisites

- macOS (Apple Silicon)
- Node.js 18+
- Rust toolchain

## Build

```bash
npm install
npm run tauri build
```

This produces:
- `.app` bundle: `src-tauri/target/release/bundle/macos/frappe-sqlite-desktop.app`
- DMG (if bundling succeeds): `src-tauri/target/release/bundle/dmg/frappe-sqlite-desktop_0.1.0_aarch64.dmg`

## Development

```bash
npm run tauri dev
```

The Vite dev server runs on `http://localhost:1420` and the Tauri app hot-reloads.

## Architecture

- **Tauri shell** (`src-tauri/src/lib.rs`) — spawns the PyInstaller sidecar on startup
- **Sidecar** (`src-tauri/binaries/frappe-sqlite-aarch64-apple-darwin`) — Frappe SQLite backend binary
- **Frontend** (`src/main.ts`) — shows a loading spinner, health-checks `http://127.0.0.1:8765`, then navigates the WebView to Frappe

## Testing

```bash
./scripts/e2e_test.sh
```

This starts the built app, waits for the Frappe server, and verifies the login page is served on port 8765.

## Known Issues / Notes

- **DMG bundling may fail** with `bundle_dmg.sh` error. The `.app` bundle is still produced and works.
- **First launch** takes 30–45 seconds while the sidecar seeds the SQLite site and starts Frappe.
- **App data** is stored in `~/Library/Application Support/FrappeSQLite/sites/`.
- **Sidecar cleanup**: when the app window is closed normally, the backend process is terminated. Force-quit (`kill -9`) may leave the sidecar running; clean up manually with `pkill -f "frappe-sqlite"` if needed.
- The PyInstaller sidecar requires its `_internal` dependencies. These are copied into `Contents/Frameworks/` inside the `.app` bundle post-build.
