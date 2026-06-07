# Frappe SQLite Desktop

Host-native macOS proof of concept for running Frappe with SQLite through a Tauri shell and PyInstaller sidecar.

The desktop app keeps executable code inside the `.app` bundle and stores mutable site data under macOS Application Support:

```text
~/Library/Application Support/FrappeSQLite/
```

Current scope:

- First-run setup screen for site name, administrator details, and data folder.
- Local PyInstaller sidecar serving Frappe on `127.0.0.1:8765`.
- SQLite site data stored under the configured data directory.
- Native menu actions for opening data/site folders and creating a site backup.
- No Docker, MariaDB, Redis, or bench process required at runtime.

After each Tauri build, run:

```bash
./scripts/sync-sidecar-into-app.sh
```

This restores the PyInstaller one-folder support layout into the generated `.app` bundle.
