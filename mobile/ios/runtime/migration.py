"""
iOS migration/seed logic — adapted from desktop and Android runners.

Differences from desktop:
- bundle_root() and sites_path() come from iOS-injected env vars
- No PyInstaller sys._MEIPASS — Python.xcframework handles extraction
- Seed site is bundled in the app payload, copied to Documents/ on first run

Differences from Android:
- No Chaquopy AssetFinder — files are real filesystem paths
- Uses shutil.copytree (no permission issues like Android read-only assets)
"""

import shutil
import os
from pathlib import Path
from runtime_paths import bundle_root, sites_path, ensure_base_dirs

# On iOS, log to stderr only (avoid file permission issues in sandbox)
os.environ.setdefault("FRAPPE_STREAM_LOGGING", "1")

DEFAULT_SITE = "sqliteonly.localhost"


def site_name() -> str:
    return os.environ.get("FRAPPE_SITE_NAME") or DEFAULT_SITE


def ensure_assets_available() -> None:
    """Copy bundled assets to the writable sites/assets/ directory."""
    root = bundle_root()

    # 1. Seed assets from bundled payload
    seed_assets = root / "resources" / "seed_site" / "sites" / "assets"
    if not seed_assets.exists():
        # Fallback: try repo-relative path (dev mode)
        seed_assets = root / "mobile" / "android" / "runtime" / "resources" / "seed_site" / "sites" / "assets"

    assets_dir = sites_path() / "assets"

    if seed_assets.exists():
        shutil.copytree(seed_assets, assets_dir, dirs_exist_ok=True)

    # 2. Frappe public assets (from frappe/frappe/public)
    source_assets = root / "apps" / "frappe" / "frappe" / "public"
    if not source_assets.exists():
        source_assets = root / "frappe" / "public"
    if not source_assets.exists():
        try:
            import frappe
            frappe_module_path = Path(frappe.__file__).parent
            source_assets = frappe_module_path / "public"
        except Exception:
            pass
    if not source_assets.exists():
        import logging
        logging.warning("Frappe public assets not found at %s; skipping copy.", source_assets)
        return

    assets_dir.mkdir(parents=True, exist_ok=True)
    target = assets_dir / "frappe"
    if target.exists() or target.is_symlink():
        return

    shutil.copytree(source_assets, target, dirs_exist_ok=True)


def seed_site_if_missing() -> None:
    """Copy the seed site to Documents/sites/<site>/ on first run."""
    ensure_base_dirs()
    ensure_assets_available()

    target_site = sites_path() / site_name()
    if target_site.exists() and (target_site / "site_config.json").exists():
        return  # Already seeded

    root = bundle_root()
    seed_root = root / "resources" / "seed_site" / "sites"
    if not seed_root.exists():
        # Fallback: try repo-relative path (dev mode)
        seed_root = root / "mobile" / "android" / "runtime" / "resources" / "seed_site" / "sites"

    if not seed_root.exists():
        raise RuntimeError(
            f"Seed site not found at {seed_root}. "
            "The iOS shell must bundle the seed_site directory in the app payload."
        )

    source_site = seed_root / DEFAULT_SITE
    if not source_site.exists():
        raise RuntimeError(f"Source site not found: {source_site}")

    shutil.copytree(source_site, target_site, dirs_exist_ok=True)

    # Copy common_site_config.json
    source_common = seed_root / "common_site_config.json"
    if source_common.exists():
        shutil.copy2(source_common, sites_path() / "common_site_config.json")

    # Copy apps.txt so frappe.get_all_apps() works
    source_apps_txt = seed_root / "apps.txt"
    if source_apps_txt.exists():
        shutil.copy2(source_apps_txt, sites_path() / "apps.txt")

    # Create logs directory to avoid FileNotFoundError from frappe logger
    (target_site / "logs").mkdir(parents=True, exist_ok=True)

    # Initialize SQLite DB if missing (no .db file)
    db_dir = target_site / "db"
    db_files = list(db_dir.glob("*.db")) if db_dir.exists() else []
    if not db_files:
        try:
            os.environ["SITES_PATH"] = str(sites_path())
            os.environ["FRAPPE_SITES_PATH"] = str(sites_path())

            import frappe
            import frappe.installer

            frappe.init(site_name(), sites_path=str(sites_path()), new_site=True)
            frappe.installer.install_db(
                db_name="site_database",
                db_type="sqlite",
                admin_password="admin",
                setup=True,
                verbose=True,
            )
            frappe.installer.install_app("frappe", verbose=True)
            frappe.destroy()
        except Exception:
            import logging
            logging.exception("Failed to initialize SQLite database for %s", site_name())
            raise


def run_migrations_if_needed() -> None:
    seed_site_if_missing()
