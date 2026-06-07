import argparse
import threading
import time
import webbrowser

from migration import run_migrations_if_needed
from server import DEFAULT_HOST, find_free_port, serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Frappe SQLite Desktop Runtime")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--migrate-only", action="store_true")
    args = parser.parse_args()

    run_migrations_if_needed()

    if args.migrate_only:
        print("Migration check completed.")
        return

    port = args.port or find_free_port()
    url = f"http://{DEFAULT_HOST}:{port}"

    if not args.no_browser:
        def open_later() -> None:
            time.sleep(2)
            webbrowser.open(url)

        threading.Thread(target=open_later, daemon=True).start()

    serve(port=port)


if __name__ == "__main__":
    main()
