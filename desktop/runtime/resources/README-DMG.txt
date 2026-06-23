Frappe SQLite Desktop — v0.1.0 (Apple Silicon)
===============================================

This is a preview build of Frappe SQLite running entirely on SQLite with no
MariaDB or Redis dependency.

System requirements
-------------------
- macOS on Apple Silicon (M1/M2/M3/M4)
- macOS 14 or later recommended

Install & run
-------------
1. Double-click the DMG to open it.
2. Drag "frappe-sqlite-desktop.app" to your Applications folder.
3. Eject the DMG.
4. Open Finder → Applications, right-click "frappe-sqlite-desktop" and choose
   "Open".

   IMPORTANT: Because this app is not notarized by Apple, the first time you
   run it macOS Gatekeeper will block a double-click. Right-click → Open is
   required the first time.

5. The first launch may take 10–20 seconds while the app copies its built-in
   SQLite site to your local Application Support folder.

6. When the login screen appears, use these default credentials:

   Administrator: Administrator
   Password: admin

Troubleshooting
---------------
- If you see "Site is running in read only mode": quit the app fully (⌘+Q),
  then relaunch. This preview build should not require manual fixes.
- If the app does not start at all, quit it and try again; the sidecar
  background server sometimes needs a moment to initialize.
- To reset the app data completely, delete this folder and relaunch:
  ~/Library/Application Support/FrappeSQLite

Support
-------
Preview build — share feedback with the developer.
