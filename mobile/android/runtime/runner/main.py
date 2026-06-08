"""
Android entry point — called from Kotlin via Chaquopy:

    val py = Python.getInstance()
    py.getModule("main").callAttr("main")

Differences from desktop:
- No argparse (Kotlin passes env vars instead)
- No webbrowser.open() (Tauri WebView handles navigation)
- Blocks indefinitely (runs in a background thread)
"""
from migration import run_migrations_if_needed
from server import find_free_port, serve


def main() -> None:
    print("[android/main] Running migrations...")
    run_migrations_if_needed()
    print("[android/main] Migrations done. Starting server...")
    port = find_free_port()
    serve(port=port)


if __name__ == "__main__":
    main()
