from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from frappe.desktop._utils import bench_root, read_site_config, resolve_sites_path, run_command, site_path, write_json
from frappe.desktop.migrate import migrate_site
from frappe.desktop.site_manager import list_sites


FRAPPE_ORG_APP_SUGGESTIONS = {
	"frappe": "https://github.com/frappe/frappe.git",
	"erpnext": "https://github.com/frappe/erpnext.git",
	"crm": "https://github.com/frappe/crm.git",
	"helpdesk": "https://github.com/frappe/helpdesk.git",
	"hrms": "https://github.com/frappe/hrms.git",
	"lms": "https://github.com/frappe/lms.git",
	"builder": "https://github.com/frappe/builder.git",
	"insights": "https://github.com/frappe/insights.git",
}


def _apps_txt(sites_path: Path) -> Path:
	return sites_path / "apps.txt"


def _available_from_apps_txt(sites_path: Path) -> list[str]:
	path = _apps_txt(sites_path)
	if not path.exists():
		return ["frappe"]
	return sorted({line.strip() for line in path.read_text().splitlines() if line.strip()})


def _app_path(app: str) -> Path | None:
	root = bench_root()
	candidates = [root / "apps" / app, root if app == "frappe" else root / app]
	for candidate in candidates:
		if (candidate / app).exists() or (candidate / "pyproject.toml").exists():
			return candidate
	return None


def _git_info(path: Path | None) -> dict[str, str | None]:
	if not path or not (path / ".git").exists():
		return {"branch": None, "commit": None}
	branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, check=False).stdout.strip() or None
	commit = run_command(["git", "rev-parse", "--short", "HEAD"], cwd=path, check=False).stdout.strip() or None
	return {"branch": branch, "commit": commit}


def resolve_app_source(source: str) -> dict[str, str]:
	"""Resolve an app source from a local path, git URL, GitHub slug, or friendly Frappe app name."""
	source_path = Path(source).expanduser()
	if source_path.exists():
		return {"app": source_path.name, "source": str(source_path.resolve()), "kind": "local_path"}
	if source.startswith(("http://", "https://", "git@", "ssh://")):
		app = source.rstrip("/").rsplit("/", 1)[-1].replace(".git", "")
		return {"app": app, "source": source, "kind": "git_url"}
	if "/" in source:
		owner, repo = source.rstrip("/").split("/", 1)
		return {"app": repo, "source": f"https://github.com/{owner}/{repo}.git", "kind": "github_slug"}
	app = source.lower().replace("_", "-")
	return {
		"app": app,
		"source": FRAPPE_ORG_APP_SUGGESTIONS.get(app, f"https://github.com/frappe/{app}.git"),
		"kind": "frappe_org_name",
	}


def list_apps(sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	available = []
	for app in _available_from_apps_txt(root):
		path = _app_path(app)
		available.append({"app": app, "path": str(path) if path else None, **_git_info(path)})
	installed_by_site = {site["site_name"]: site["installed_apps"] for site in list_sites(root)}
	return {
		"available_apps": available,
		"installed_by_site": installed_by_site,
		"suggested_apps": [
			{"app": app, "source": source} for app, source in sorted(FRAPPE_ORG_APP_SUGGESTIONS.items()) if app != "frappe"
		],
	}


def add_app(source: str, branch: str | None = None, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	root.mkdir(parents=True, exist_ok=True)
	apps_txt = _apps_txt(root)
	apps = set(_available_from_apps_txt(root))
	resolved = resolve_app_source(source)
	app_name = resolved["app"]
	if resolved["kind"] == "local_path":
		target = bench_root() / "apps" / app_name
		target.parent.mkdir(parents=True, exist_ok=True)
		if not target.exists():
			target.symlink_to(Path(resolved["source"]), target_is_directory=True)
	else:
		target = bench_root() / "apps" / app_name
		target.parent.mkdir(parents=True, exist_ok=True)
		command = ["git", "clone", resolved["source"], str(target)]
		if branch:
			command[2:2] = ["--branch", branch]
		if not target.exists():
			run_command(command, cwd=bench_root())
	apps.add(app_name)
	apps_txt.parent.mkdir(parents=True, exist_ok=True)
	apps_txt.write_text("\n".join(sorted(apps)) + "\n")
	return {"app": app_name, "available": True, "source": resolved["source"], "kind": resolved["kind"]}


def _installed_apps(site_name: str, sites_path: Path) -> list[str]:
	return sorted(read_site_config(site_name, sites_path).get("installed_apps") or [])


def install_app(site_name: str, app_name: str, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	if not site_path(site_name, root).exists():
		raise FileNotFoundError(f"Site missing: {site_name}")
	if app_name not in _available_from_apps_txt(root):
		add_app(app_name, sites_path=root)
	import frappe
	from frappe.installer import install_app as frappe_install_app

	frappe.init(site=site_name, sites_path=str(root))
	try:
		frappe.connect()
		frappe_install_app(app_name, force=False)
		frappe.db.commit()
	finally:
		frappe.destroy()
	migrate_site(site_name, sites_path=root)
	return {"site_name": site_name, "app": app_name, "installed": True}


def uninstall_app(site_name: str, app_name: str, force: bool = False, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	config = read_site_config(site_name, root)
	apps = list(config.get("installed_apps") or [])
	if app_name not in apps:
		return {"site_name": site_name, "app": app_name, "uninstalled": False, "reason": "not_installed"}
	if app_name == "frappe" and not force:
		raise ValueError("Refusing to uninstall frappe without force=True")
	apps.remove(app_name)
	config["installed_apps"] = apps
	write_json(site_path(site_name, root) / "site_config.json", config)
	migrate_site(site_name, sites_path=root)
	return {"site_name": site_name, "app": app_name, "uninstalled": True}


def update_app(app_name: str | None = None) -> list[dict[str, Any]]:
	apps = [app_name] if app_name else [entry["app"] for entry in list_apps()["available_apps"]]
	results = []
	for app in apps:
		path = _app_path(app)
		if not path or not (path / ".git").exists():
			results.append({"app": app, "updated": False, "reason": "not_git_backed"})
			continue
		run_command(["git", "pull", "--ff-only"], cwd=path)
		results.append({"app": app, "updated": True})
	return results


def remove_app(app_name: str, force: bool = False, sites_path: str | Path | None = None) -> dict[str, Any]:
	root = resolve_sites_path(sites_path)
	installed = [site for site, apps in list_apps(root)["installed_by_site"].items() if app_name in apps]
	if installed and not force:
		raise ValueError(f"App {app_name} is installed on sites: {', '.join(installed)}")
	apps = set(_available_from_apps_txt(root))
	apps.discard(app_name)
	_apps_txt(root).write_text("\n".join(sorted(apps)) + "\n")
	path = _app_path(app_name)
	if path and path.parent.name == "apps":
		shutil.rmtree(path)
	return {"app": app_name, "removed": True}


def _main() -> None:
	parser = argparse.ArgumentParser(description="Local SQLite app lifecycle helpers")
	sub = parser.add_subparsers(dest="command", required=True)
	sub.add_parser("list")
	add = sub.add_parser("add")
	add.add_argument("source")
	add.add_argument("--branch")
	install = sub.add_parser("install")
	install.add_argument("site")
	install.add_argument("app")
	args = parser.parse_args()
	if args.command == "list":
		print(json.dumps(list_apps(), indent=2))
	elif args.command == "add":
		print(json.dumps(add_app(args.source, branch=args.branch), indent=2))
	elif args.command == "install":
		print(json.dumps(install_app(args.site, args.app), indent=2))


if __name__ == "__main__":
	_main()
