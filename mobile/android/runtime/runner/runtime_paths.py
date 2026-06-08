"""
Android-aware runtime paths for Frappe SQLite.

On Android, all paths are injected via environment variables set by Kotlin
before Python starts. There is no ~/Library/Application Support.

Environment variables expected:
  FRAPPE_SQLITE_DATA_DIR     → app's filesDir (private app storage)
  FRAPPE_SQLITE_BUNDLE_ROOT  → where Chaquopy extracted Python sources
"""
import os
from pathlib import Path

PRODUCT_NAME = "FrappeSQLite"


def app_data_root() -> Path:
    override = os.environ.get("FRAPPE_SQLITE_DATA_DIR")
    if override:
        return Path(override)
    # Fallback for local dev (not Android)
    return Path.home() / ".frappe-sqlite-mobile"


def bundle_root() -> Path:
    override = os.environ.get("FRAPPE_SQLITE_BUNDLE_ROOT")
    if override:
        return Path(override)
    # Fallback: walk up from this file to repo root
    return Path(__file__).resolve().parents[4]


def sites_path() -> Path:
    return app_data_root() / "sites"


def logs_path() -> Path:
    return app_data_root() / "logs"


def ensure_base_dirs() -> None:
    app_data_root().mkdir(parents=True, exist_ok=True)
    sites_path().mkdir(parents=True, exist_ok=True)
    logs_path().mkdir(parents=True, exist_ok=True)
