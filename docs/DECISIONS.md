# DECISIONS

## 2026-06-07T01:20Z — Adapt plan to actual bench setup

**Decision:** Use `sqliteonly.localhost` as the site name and `frappe`-only (no erpnext) for packaging.

**Rationale:** The actual bench only has `frappe` installed. The plan assumed `site1.local` and `erpnext`, but these don't exist. The packaging approach works the same regardless of which apps are installed.

**Impact:**
- Site name in all runner scripts: `sqliteonly.localhost`
- No erpnext-specific acceptance tests (Customer, Item, Sales Invoice)
- Will use standard Frappe DocTypes (ToDo, User) for smoke tests instead

## 2026-06-07T01:48Z — PyInstaller assets duplication

**Decision:** Include `sites/assets` twice in PyInstaller spec — once as `sites/assets` and once as `assets`.

**Rationale:** Frappe's `get_assets_json()` looks for `assets/assets.json` relative to cwd. The actual assets live in `sites/assets/`. In the frozen binary, `bundle_root()` resolves to `sys._MEIPASS`. By copying `sites/assets` to both `sites/assets` (for seed site references) and `assets` (for `get_assets_json`), both code paths work without modifying Frappe.

**Impact:** Binary size increases slightly but no source patches needed.

## 2026-06-07T01:42Z — passlib hidden imports for PyInstaller

**Decision:** Use `collect_submodules("passlib.handlers")` instead of individual handler names.

**Rationale:** `passlib` dynamically imports hash handlers at runtime. PyInstaller cannot detect these. After hitting `pbkdf2`, then `argon2`, we switched to collecting all submodules.

**Impact:** Build time increased slightly but all password hash schemes are available.

## 2026-06-07T01:35Z — Assets symlink for bundled_assets resolution

**Decision:** Create symlink `assets -> sites/assets` at bench root.

**Rationale:** Frappe's `get_assets_json()` calls `frappe.read_file("assets/assets.json")` which resolves relative to current working directory. The actual assets are in `sites/assets/`. Without the symlink, `bundled_asset()` gets None and raises AttributeError during template rendering.

**Impact:** Login page and all template rendering now works. For PyInstaller, we duplicate assets in the spec instead of relying on symlinks.

## 2026-06-07T01:19Z — WAL checkpoint to recover malformed DB

**Decision:** Run `PRAGMA wal_checkpoint(TRUNCATE)` to recover from "database disk image is malformed" error.

**Rationale:** The integrity check on the main DB file was OK, but the WAL file may have been corrupted. A truncate checkpoint forces all WAL pages into the main DB and resets the WAL.

**Impact:** Database recovered successfully, no data loss observed.
