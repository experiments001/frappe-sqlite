import shutil
import os
from pathlib import Path
from runtime_paths import bundle_root, sites_path, ensure_base_dirs

DEFAULT_SITE = "sqliteonly.localhost"

def site_name() -> str:
    return os.environ.get("FRAPPE_SITE_NAME") or DEFAULT_SITE

def ensure_assets_available() -> None:
    root = bundle_root()
    source_assets = root / "frappe" / "public"
    if not source_assets.exists():
        source_assets = root / "apps" / "frappe" / "frappe" / "public"
    if not source_assets.exists():
        raise RuntimeError(f"Frappe public assets not found: {source_assets}")

    assets_dir = sites_path() / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    target = assets_dir / "frappe"
    if target.exists() or target.is_symlink():
        return

    shutil.copytree(source_assets, target, dirs_exist_ok=True)

def seed_site_if_missing() -> None:
    ensure_base_dirs()
    ensure_assets_available()
    target_site = sites_path() / site_name()
    if target_site.exists() and (target_site / "site_config.json").exists():
        return

    root = bundle_root()
    # Try frozen path first (resources at bundle root), then dev paths
    seed_root = root / "resources" / "seed_site" / "sites"
    if not seed_root.exists():
        seed_root = root / "desktop" / "runtime" / "resources" / "seed_site" / "sites"
    if not seed_root.exists():
        seed_root = root / "desktop_runtime" / "resources" / "seed_site" / "sites"

    if not seed_root.exists():
        raise RuntimeError(f"Seed site not found: {seed_root}")

    source_site = seed_root / DEFAULT_SITE
    if not source_site.exists():
        raise RuntimeError(f"Source site not found: {source_site}")

    shutil.copytree(source_site, target_site, dirs_exist_ok=True)
    source_common = seed_root / "common_site_config.json"
    if source_common.exists():
        shutil.copy2(source_common, sites_path() / "common_site_config.json")

    # Copy apps.txt so frappe.get_all_apps() works
    source_apps_txt = seed_root / "apps.txt"
    if source_apps_txt.exists():
        shutil.copy2(source_apps_txt, sites_path() / "apps.txt")

    # Create logs directory to avoid FileNotFoundError from frappe logger
    (target_site / "logs").mkdir(parents=True, exist_ok=True)

def run_migrations_if_needed() -> None:
    seed_site_if_missing()
