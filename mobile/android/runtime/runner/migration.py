"""
Android migration/seed logic — adapted from desktop/runtime/runner/migration.py.

Differences from desktop:
- bundle_root() and sites_path() come from Android-injected env vars
- No PyInstaller sys._MEIPASS — Chaquopy handles extraction
- Seed site lives in APK assets, extracted to filesDir by Kotlin before this runs
"""
import shutil
import os
from pathlib import Path
from runner.runtime_paths import bundle_root, sites_path, ensure_base_dirs

# On Android, log to stderr only (avoid file permission/CWD issues)
os.environ.setdefault("FRAPPE_STREAM_LOGGING", "1")

DEFAULT_SITE = "sqliteonly.localhost"


def _copytree(src: Path, dst: Path) -> None:
    """Copy tree without preserving permissions (avoids Android read-only issues)."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        dest_item = dst / item.name
        if item.is_dir():
            _copytree(item, dest_item)
        else:
            try:
                shutil.copyfile(item, dest_item)
                os.chmod(dest_item, 0o644)
            except PermissionError:
                pass  # Skip files we can't copy


def site_name() -> str:
    return os.environ.get("FRAPPE_SITE_NAME") or DEFAULT_SITE


def ensure_assets_available() -> None:
    root = bundle_root()
    # On Android: seed assets are pre-extracted by Kotlin to bundle_root/resources/seed_site/
    seed_assets = root / "resources" / "seed_site" / "sites" / "assets"

    assets_dir = sites_path() / "assets"

    if seed_assets.exists():
        _copytree(seed_assets, assets_dir)

    # Frappe public assets — in Chaquopy sourceSet
    # On Android, frappe is in AssetFinder; find it via module path
    source_assets = root / "frappe" / "public"
    if not source_assets.exists():
        source_assets = root / "apps" / "frappe" / "frappe" / "public"
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

    _copytree(source_assets, target)


def seed_site_if_missing() -> None:
    ensure_base_dirs()
    ensure_assets_available()
    target_site = sites_path() / site_name()
    if target_site.exists() and (target_site / "site_config.json").exists():
        return

    root = bundle_root()
    seed_root = root / "resources" / "seed_site" / "sites"
    if not seed_root.exists():
        raise RuntimeError(
            f"Seed site not found at {seed_root}. "
            "Kotlin must extract APK assets to bundle_root before starting Python."
        )

    source_site = seed_root / DEFAULT_SITE
    if not source_site.exists():
        raise RuntimeError(f"Source site not found: {source_site}")

    _copytree(source_site, target_site)
    source_common = seed_root / "common_site_config.json"
    if source_common.exists():
        shutil.copyfile(source_common, sites_path() / "common_site_config.json")

    source_apps_txt = seed_root / "apps.txt"
    if source_apps_txt.exists():
        shutil.copyfile(source_apps_txt, sites_path() / "apps.txt")

    (target_site / "logs").mkdir(parents=True, exist_ok=True)

    # Initialize SQLite DB if missing
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
