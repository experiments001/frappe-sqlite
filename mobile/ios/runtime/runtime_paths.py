"""
iOS-aware runtime paths for Frappe SQLite.

On iOS, all paths come from environment variables set by the Swift/Briefcase
shell before Python starts:

  FRAPPE_DATA_DIR       → app sandbox Documents/ (writable)
  FRAPPE_BUNDLE_ROOT    → bundled read-only payload (apps/, sites/assets, seed)

There is no ~/Library/Application Support on iOS.
"""

import os
from pathlib import Path

PRODUCT_NAME = "FrappeSQLite"


def app_data_root() -> Path:
    """Return the writable app data directory (iOS Documents/)."""
    override = os.environ.get("FRAPPE_DATA_DIR")
    if override:
        return Path(override)
    # Fallback for local dev testing (not iOS)
    return Path.home() / ".frappe-sqlite-ios"


def bundle_root() -> Path:
    """Return the bundled read-only payload directory."""
    override = os.environ.get("FRAPPE_BUNDLE_ROOT")
    if override:
        return Path(override)
    # Fallback: walk up from this file to repo root
    # runtime/runtime_paths.py → mobile/ios/runtime → mobile/ios → repo root
    return Path(__file__).resolve().parents[3]


def sites_path() -> Path:
    return app_data_root() / "sites"


def logs_path() -> Path:
    return app_data_root() / "logs"


def ensure_base_dirs() -> None:
    app_data_root().mkdir(parents=True, exist_ok=True)
    sites_path().mkdir(parents=True, exist_ok=True)
    logs_path().mkdir(parents=True, exist_ok=True)
