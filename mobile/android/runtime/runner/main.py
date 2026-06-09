"""
Android entry point — called from Kotlin via Chaquopy:

    val py = Python.getInstance()
    py.getModule("main").callAttr("main")

Differences from desktop:
- No argparse (Kotlin passes env vars instead)
- No webbrowser.open() (Tauri WebView handles navigation)
- Blocks indefinitely (runs in a background thread)
"""
import sys

from runner.migration import run_migrations_if_needed
from runner.server import find_free_port, serve


def main() -> None:
    print("[android/main] Running migrations...")
    try:
        run_migrations_if_needed()
    except Exception as mig_err:
        print(f"[android/main] Migrations FAILED: {mig_err}", file=sys.stderr)
        raise

    print("[android/main] Migrations done. Starting server...")
    try:
        port = find_free_port()
        serve(port=port)
    except Exception as serve_err:
        print(f"[android/main] Server FAILED: {serve_err}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
