import os
import sys
from pathlib import Path

PRODUCT_NAME = "FrappeSQLite"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    # desktop/runtime/runner/runtime_paths.py -> repo root
    return Path(__file__).resolve().parents[3]


def app_data_root() -> Path:
    override = os.environ.get("FRAPPE_SQLITE_DATA_DIR")
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
