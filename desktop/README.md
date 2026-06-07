# Frappe SQLite Desktop

Optional macOS desktop packaging for this Frappe-compatible SQLite fork.

The desktop layer is a consumer of the SQLite runtime. It must not define core Frappe behavior.

## Layout

```text
desktop/
  shell/       Tauri shell
  runtime/     Python runner used by the sidecar/dev mode
  scripts/     build, sync, run, and verification helpers
```

## Generated Artifacts

These are build outputs, not source of truth:

```text
desktop/shell/src-tauri/binaries/_internal/
desktop/shell/src-tauri/target/
desktop/shell/src-tauri/gen/
desktop/shell/dist/
*.app
*.dmg
```

## Current PoC Flow

```bash
./desktop/scripts/build-sidecar.sh
./desktop/scripts/sync-sidecar.sh
./desktop/scripts/verify-bundle.sh
./desktop/scripts/run-packaged.sh
```

The current sidecar build script still bridges through the historical `sqlitepoc` build checkout. Set `SQLITEPOC_ROOT` if that checkout lives elsewhere.

Release cleanup still needs the PyInstaller spec/resources moved into this repo so `build-sidecar.sh` no longer depends on that historical checkout.

## Runtime Data

Mutable site data lives outside the app bundle:

```text
~/Library/Application Support/FrappeSQLite/
```
