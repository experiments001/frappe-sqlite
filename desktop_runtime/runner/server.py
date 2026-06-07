import os
import socket
import sys
from pathlib import Path
from werkzeug.serving import run_simple
from runtime_paths import bundle_root, sites_path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_SITE = "sqliteonly.localhost"

def site_name() -> str:
    return os.environ.get("FRAPPE_SITE_NAME") or DEFAULT_SITE

def find_free_port(start: int = 8765, end: int = 8865) -> int:
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex((DEFAULT_HOST, port)) != 0:
                return port
    raise RuntimeError("No free local port found")

def configure_python_paths() -> None:
    root = bundle_root()
    for p in [root / "apps" / "frappe", root]:
        if p.exists():
            sys.path.insert(0, str(p))

def configure_frappe_env() -> None:
    os.environ.setdefault("FRAPPE_SITE_NAME", site_name())
    os.environ.setdefault("SITES_PATH", str(sites_path()))
    os.environ.setdefault("FRAPPE_SITES_PATH", str(sites_path()))
    os.environ.setdefault("FRAPPE_SQLITE_DESKTOP", "1")
    os.environ.setdefault("NO_REDIS", "1")
    os.environ.setdefault("NO_MARIADB", "1")
    os.environ.setdefault("FRAPPE_STREAM_LOGGING", "1")

def serve(port: int | None = None) -> int:
    configure_python_paths()
    configure_frappe_env()
    selected_port = port or find_free_port()

    # Change to bench root so frappe can find assets/assets.json etc.
    root = bundle_root()
    os.chdir(root)

    import frappe.app
    frappe.app._site = site_name()
    frappe.app._sites_path = str(sites_path())

    from frappe.app import application_with_statics
    application = application_with_statics()
    print(f"Starting Frappe SQLite on http://{DEFAULT_HOST}:{selected_port}")
    print(f"Sites path: {sites_path()}")
    run_simple(
        hostname=DEFAULT_HOST,
        port=selected_port,
        application=application,
        use_reloader=False,
        use_debugger=False,
        threaded=True,
    )
    return selected_port
