"""
iOS entry point — called once, on a background thread, by the iOS shell.

This is the single Python change for iOS (per the build plan §5):
- Same runner as desktop/Android
- In-process (no subprocess — iOS bans them)
- iOS sandbox paths (Documents/)
- Embedded mode flags

Called by:
- Lane A (Briefcase): app.py → ios_main.start_background()
- Lane B (Swift):     PythonRunner.swift → PyRun_SimpleString("import ios_main; ios_main.start()")
"""

import os
import sys
import threading


def _configure_paths():
    """Set up sys.path so frappe/ is importable."""
    # FRAPPE_BUNDLE_ROOT is set by the Swift/Briefcase shell to the bundled payload dir
    root = os.environ.get("FRAPPE_BUNDLE_ROOT")
    if root:
        for p in (os.path.join(root, "apps", "frappe"), root):
            if os.path.isdir(p) and p not in sys.path:
                sys.path.insert(0, p)
    # Also ensure our own runtime dir is on path for imports
    runtime_dir = os.path.dirname(os.path.abspath(__file__))
    if runtime_dir not in sys.path:
        sys.path.insert(0, runtime_dir)


def start():
    """Blocking entry point. Runs Werkzeug in-process on this thread."""
    _configure_paths()

    # Force embedded/iOS mode
    os.environ.setdefault("ERPNEXT_SQLITE_DESKTOP", "1")
    os.environ.setdefault("EMBEDDED_INPROCESS", "1")
    os.environ.setdefault("NO_REDIS", "1")
    os.environ.setdefault("NO_MARIADB", "1")
    os.environ.setdefault("FRAPPE_STREAM_LOGGING", "1")

    # Writable data dir = iOS app sandbox Documents/
    data_dir = os.environ.get("FRAPPE_DATA_DIR")
    if data_dir:
        os.environ.setdefault("ERPNEXT_SQLITE_DATA_DIR", data_dir)

    # Import from the iOS runtime package (same files as desktop, just iOS paths)
    from migration import run_migrations_if_needed  # noqa: F401
    from server import serve  # noqa: F401

    # Seed site + assets on first run (same pattern as desktop/Android)
    run_migrations_if_needed()

    # Start Werkzeug (blocks; runs on background thread)
    port = int(os.environ.get("FRAPPE_PORT", "8765"))
    serve(port=port)


def start_background():
    """Non-blocking variant for Briefcase (Lane A).

    Starts Frappe on a daemon thread so the UI thread stays free.
    Returns the thread handle.
    """
    t = threading.Thread(target=start, name="frappe-wsgi", daemon=True)
    t.start()
    return t


# Convenience: if run directly (e.g., from Briefcase app.py)
if __name__ == "__main__":
    start()
