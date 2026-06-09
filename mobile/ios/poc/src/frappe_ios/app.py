"""
FrappeSQLite iOS App — Briefcase entrypoint (Lane A).

This is the thin bootstrap that Briefcase calls on app launch.
It:
1. Sets up environment variables for the iOS runtime
2. Adds the bundled frappe/ core and shims to sys.path
3. Starts the Frappe Werkzeug server in a background thread
4. Keeps the Briefcase/Toga event loop alive
"""

import os
import sys
import time


def _setup_paths():
    """Configure sys.path so frappe/ and shims are importable."""
    # This file: poc/src/frappe_ios/app.py
    # src/ dir:  poc/src/
    # shims/:    poc/src/shims/
    # frappe/:   repo_root/frappe/
    # runtime/:  repo_root/mobile/ios/runtime/

    app_file = os.path.abspath(__file__)
    src_dir = os.path.dirname(os.path.dirname(app_file))  # poc/src/
    poc_dir = os.path.dirname(src_dir)                      # poc/
    ios_dir = os.path.dirname(poc_dir)                      # mobile/ios/
    mobile_dir = os.path.dirname(ios_dir)                   # mobile/
    repo_root = os.path.dirname(mobile_dir)                 # repo root

    # Add shims first (so they shadow real packages)
    shims_path = os.path.join(src_dir, "shims")
    if os.path.isdir(shims_path) and shims_path not in sys.path:
        sys.path.insert(0, shims_path)

    # Add frappe/ core
    frappe_path = os.path.join(repo_root, "frappe")
    if os.path.isdir(frappe_path) and frappe_path not in sys.path:
        sys.path.insert(0, frappe_path)

    # Add runtime/ (for ios_main, server, migration, runtime_paths)
    runtime_path = os.path.join(repo_root, "mobile", "ios", "runtime")
    if os.path.isdir(runtime_path) and runtime_path not in sys.path:
        sys.path.insert(0, runtime_path)

    return repo_root


def main():
    """Briefcase entrypoint."""
    print("[FrappeSQLite] iOS app starting...")

    repo_root = _setup_paths()

    # Set iOS-specific environment variables
    # Briefcase provides BRIEFCASE_APP_DIR pointing to the app bundle
    app_dir = os.environ.get("BRIEFCASE_APP_DIR", os.path.expanduser("~/.frappe-sqlite-ios"))
    data_dir = os.path.join(app_dir, "Documents")
    os.makedirs(data_dir, exist_ok=True)

    os.environ["FRAPPE_BUNDLE_ROOT"] = repo_root
    os.environ["FRAPPE_DATA_DIR"] = data_dir
    os.environ["FRAPPE_PORT"] = "8765"

    # Start Frappe server in background thread
    try:
        import ios_main
        print("[FrappeSQLite] Starting Frappe server on background thread...")
        thread = ios_main.start_background()
        print(f"[FrappeSQLite] Server thread: {thread.name} (daemon={thread.daemon})")
    except Exception as e:
        print(f"[FrappeSQLite] ERROR starting server: {e}")
        import traceback
        traceback.print_exc()
        return

    # Keep app alive — Briefcase/Toga event loop
    print("[FrappeSQLite] Server thread started. Keeping app alive...")
    while True:
        time.sleep(1)


# Toga/Briefcase app class (used if template is Toga)
# For the PoC, the simple main() above is sufficient.
# The Toga template will call main() automatically.
