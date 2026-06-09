import os
import sys

# Save original stdout file descriptor and redirect stdout→stderr at OS level
# before ANY frappe imports, so their DDL/logging noise goes to stderr.
_original_stdout_fd = os.dup(sys.stdout.fileno())
_stderr_fd = sys.stderr.fileno()

def _restore_stdout() -> None:
    os.dup2(_original_stdout_fd, sys.stdout.fileno())

def _redirect_stdout_to_stderr() -> None:
    os.dup2(_stderr_fd, sys.stdout.fileno())

_redirect_stdout_to_stderr()

import argparse
import json
import threading
import time
import traceback
from typing import Any

from server import configure_frappe_env, configure_python_paths


def _pulse_progress(stop_event: threading.Event, stage: str, message: str, pct: int) -> None:
    """Emit progress every 5s so the UI knows we're not frozen."""
    while not stop_event.is_set():
        time.sleep(5)
        if not stop_event.is_set():
            emit_progress(stage, message, pct)


def emit_progress(stage: str, message: str, pct: int | None = None) -> None:
    """Emit a progress event line to the real stdout with PROGRESS: sentinel."""
    payload = {"stage": stage, "message": message}
    if pct is not None:
        payload["pct"] = pct
    _restore_stdout()
    print(f"PROGRESS:{json.dumps(payload)}", flush=True)
    _redirect_stdout_to_stderr()


def emit_result(data: Any) -> None:
    """Emit the final result to the real stdout with RESULT: sentinel."""
    _restore_stdout()
    print(f"RESULT:{json.dumps(data)}", flush=True)
    _redirect_stdout_to_stderr()


def run_lifecycle(args: list[str]) -> int:
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    configure_python_paths()
    configure_frappe_env()

    parser = argparse.ArgumentParser(prog="frappe-sqlite lifecycle")
    sub = parser.add_subparsers(dest="group", required=True)

    # site
    site = sub.add_parser("site", help="Site operations")
    site_sub = site.add_subparsers(dest="command", required=True)

    site_sub.add_parser("list", help="List sites")

    create = site_sub.add_parser("create", help="Create a site")
    create.add_argument("site")
    create.add_argument("--force", action="store_true")
    create.add_argument("--full-install", action="store_true")
    create.add_argument("--complete-setup", action="store_true")
    create.add_argument("--admin-password", default=None)
    create.add_argument("--timezone", default=None)
    create.add_argument("--country", default=None)
    create.add_argument("--currency", default=None)
    create.add_argument("--language", default=None)

    drop = site_sub.add_parser("drop", help="Drop a site")
    drop.add_argument("site")
    drop.add_argument("--force", action="store_true")
    drop.add_argument("--with-backup", action="store_true")

    clone = site_sub.add_parser("clone", help="Clone a site")
    clone.add_argument("source")
    clone.add_argument("target")
    clone.add_argument("--force", action="store_true")

    export = site_sub.add_parser("export", help="Export a site")
    export.add_argument("site")
    export.add_argument("--output", required=True)

    import_ = site_sub.add_parser("import", help="Import a site")
    import_.add_argument("input")
    import_.add_argument("--site", default=None)
    import_.add_argument("--force", action="store_true")

    # app
    app = sub.add_parser("app", help="App operations")
    app_sub = app.add_subparsers(dest="command", required=True)

    app_sub.add_parser("list", help="List apps")

    add = app_sub.add_parser("add", help="Add an app")
    add.add_argument("source")
    add.add_argument("--branch", default=None)

    install = app_sub.add_parser("install", help="Install an app on a site")
    install.add_argument("site")
    install.add_argument("app")

    uninstall = app_sub.add_parser("uninstall", help="Uninstall an app from a site")
    uninstall.add_argument("site")
    uninstall.add_argument("app")
    uninstall.add_argument("--force", action="store_true")

    update = app_sub.add_parser("update", help="Update apps")
    update.add_argument("--app", default=None)

    remove = app_sub.add_parser("remove", help="Remove an app")
    remove.add_argument("app")
    remove.add_argument("--force", action="store_true")

    # migrate
    migrate = sub.add_parser("migrate", help="Migration operations")
    migrate_sub = migrate.add_subparsers(dest="command", required=True)

    migrate_site = migrate_sub.add_parser("site", help="Migrate a site")
    migrate_site.add_argument("site")

    migrate_sub.add_parser("all", help="Migrate all sites")

    # rebuild
    sub.add_parser("rebuild", help="Rebuild the desktop app")

    # check-rebuild
    sub.add_parser("check-rebuild", help="Check if rebuild is needed")

    parsed = parser.parse_args(args)

    try:
        result = _dispatch(parsed)
        emit_result(result)
        return 0
    except SystemExit:
        raise
    except Exception as exc:
        emit_result(
            {"ok": False, "error": str(exc), "stderr": traceback.format_exc()}
        )
        return 1


def _dispatch(args: argparse.Namespace) -> Any:
    from frappe.desktop.site_manager import (
        clone_site,
        create_site,
        drop_site,
        export_site,
        import_site,
        list_sites,
    )
    from frappe.desktop.app_manager import (
        add_app,
        install_app,
        list_apps,
        remove_app,
        uninstall_app,
        update_app,
    )
    from frappe.desktop.migrate import migrate_all_sites, migrate_site
    from frappe.desktop.build import build_desktop_app, check_rebuild_needed

    group = args.group
    command = getattr(args, "command", None)

    if group == "site":
        if command == "list":
            return list_sites()
        if command == "create":
            emit_progress("init", "Initializing...", 5)
            stop_pulse = threading.Event()
            pulse_thread = threading.Thread(
                target=_pulse_progress,
                args=(stop_pulse, "working", "Installing Frappe framework, please wait...", 50),
                daemon=True,
            )
            pulse_thread.start()
            try:
                result = create_site(
                    args.site,
                    force=args.force,
                    admin_password=args.admin_password,
                    timezone=args.timezone,
                    country=args.country,
                    currency=args.currency,
                    language=args.language,
                    complete_setup=args.complete_setup,
                    use_frappe_installer=args.full_install,
                )
            finally:
                stop_pulse.set()
                pulse_thread.join(timeout=1)
            emit_progress("complete", "Site created.", 100)
            return result
        if command == "drop":
            return drop_site(
                args.site,
                force=args.force,
                no_backup=not args.with_backup,
            )
        if command == "clone":
            return clone_site(args.source, args.target, force=args.force)
        if command == "export":
            return export_site(args.site, args.output)
        if command == "import":
            return import_site(args.input, site_name=args.site, force=args.force)

    if group == "app":
        if command == "list":
            return list_apps()
        if command == "add":
            return add_app(args.source, branch=args.branch)
        if command == "install":
            return install_app(args.site, args.app)
        if command == "uninstall":
            return uninstall_app(args.site, args.app, force=args.force)
        if command == "update":
            return update_app(app_name=args.app)
        if command == "remove":
            return remove_app(args.app, force=args.force)

    if group == "migrate":
        if command == "site":
            return migrate_site(args.site)
        if command == "all":
            return migrate_all_sites()

    if group == "rebuild":
        return build_desktop_app()

    if group == "check-rebuild":
        return check_rebuild_needed()

    raise ValueError(f"Unknown command: {group} {command}")
